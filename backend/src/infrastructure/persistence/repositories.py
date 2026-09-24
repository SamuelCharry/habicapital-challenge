from collections.abc import Iterable, Sequence
from uuid import UUID

from django.db import IntegrityError, connection
from django.db.models import Sum

from src.domain.entities import Account, EXTERNAL_FUNDING_ID, LedgerEntry, TransferOperation
from src.domain.errors import AccountNotFound, DuplicateHandle, DuplicateIdempotencyKey, SharedExpenseNotFound
from src.domain.money import Money
from src.domain.repositories import AccountRepository, LedgerRepository, TransferOperationRepository, SharedExpenseRepository
from src.domain.shared_expenses import SharedExpense, Participant, Share
from .models import AccountModel, LedgerEntryModel, TransferOperationModel, SharedExpenseModel, ParticipantModel


def account_entity(row: AccountModel) -> Account:
    return Account(row.id, row.handle, row.display_name, row.allows_negative_balance)


class DjangoAccountRepository(AccountRepository):
    def lock_for_update(self, account_ids: Sequence[UUID]) -> list[Account]:
        ids = set(account_ids)
        rows = list(AccountModel.objects.filter(pk__in=ids).order_by("id").select_for_update())
        if len(rows) != len(ids):
            raise AccountNotFound("Account does not exist.")
        return [account_entity(row) for row in rows]

    def add(self, account: Account) -> Account:
        try:
            AccountModel.objects.create(
                id=account.id, handle=account.handle, display_name=account.display_name,
                allows_negative_balance=account.allows_negative_balance,
            )
        except IntegrityError as exc:
            cause = exc.__cause__
            constraint = getattr(getattr(cause, "diag", None), "constraint_name", "") or ""
            if getattr(cause, "sqlstate", None) == "23505" and "handle" in constraint:
                raise DuplicateHandle("Handle already exists.") from exc
            raise
        return account

    def get(self, account_id: UUID) -> Account:
        try:
            return account_entity(AccountModel.objects.get(pk=account_id))
        except AccountModel.DoesNotExist as exc:
            raise AccountNotFound("Account does not exist.") from exc

    def get_by_handle(self, handle: str) -> Account:
        try:
            return account_entity(AccountModel.objects.get(handle=handle))
        except AccountModel.DoesNotExist as exc:
            raise AccountNotFound("Account does not exist.") from exc

    def handles_for(self, account_ids: Iterable[UUID]) -> dict[UUID, str]:
        return dict(AccountModel.objects.filter(pk__in=account_ids).values_list("id", "handle"))

    def list_user_accounts(self) -> list[Account]:
        rows = AccountModel.objects.exclude(pk=EXTERNAL_FUNDING_ID).order_by("handle")
        return [account_entity(row) for row in rows]

    def balance_of(self, account_id: UUID) -> Money:
        self.get(account_id)
        total = LedgerEntryModel.objects.filter(account_id=account_id).aggregate(total=Sum("amount_minor"))["total"]
        return Money(int(total or 0))


class DjangoLedgerRepository(LedgerRepository):
    def append(self, entries: Sequence[LedgerEntry]) -> None:
        if not connection.in_atomic_block:
            raise RuntimeError("Ledger writes require an application transaction.")
        LedgerEntryModel.objects.bulk_create([
            LedgerEntryModel(
                id=e.id, account_id=e.account_id, counterparty_id=e.counterparty_id,
                operation_id=e.operation_id, operation_type=e.operation_type,
                amount_minor=e.money.amount_minor, currency=e.money.currency,
                created_at=e.created_at,
            )
            for e in entries
        ])

    def entries_for(self, account_id: UUID) -> list[LedgerEntry]:
        return [
            LedgerEntry(
                row.id, row.account_id, row.counterparty_id, row.operation_id,
                row.operation_type, Money(row.amount_minor, row.currency), row.created_at,
            )
            for row in LedgerEntryModel.objects.filter(account_id=account_id)
        ]

    def total_balance(self) -> Money:
        total = LedgerEntryModel.objects.aggregate(total=Sum("amount_minor"))["total"]
        return Money(int(total or 0))


class DjangoTransferOperationRepository(TransferOperationRepository):
    def link_expense(self, operation_id: UUID, expense_id: UUID) -> None:
        if not connection.in_atomic_block:
            raise RuntimeError('Transfer context requires an application transaction.')
        TransferOperationModel.objects.filter(operation_id=operation_id).update(shared_expense_id=expense_id)

    def claim(self, key: str, fingerprint: str, operation_id: UUID) -> None:
        if not connection.in_atomic_block:
            raise RuntimeError("Transfer claims require an application transaction.")
        try:
            TransferOperationModel.objects.create(
                idempotency_key=key, request_fingerprint=fingerprint, operation_id=operation_id,
            )
        except IntegrityError as exc:
            cause = exc.__cause__
            constraint = getattr(getattr(cause, "diag", None), "constraint_name", None)
            if getattr(cause, "sqlstate", None) == "23505" and constraint == "transfer_idempotency_key_unique":
                raise DuplicateIdempotencyKey("Idempotency key already exists.") from exc
            raise

    def get(self, key: str) -> TransferOperation:
        row = TransferOperationModel.objects.get(idempotency_key=key)
        return TransferOperation(
            row.idempotency_key, row.request_fingerprint, row.operation_id,
            Money(int(row.source_balance_minor), row.currency),
            Money(int(row.destination_balance_minor), row.currency),
        )

    def complete(self, key: str, source_balance: Money, destination_balance: Money) -> None:
        if not connection.in_atomic_block:
            raise RuntimeError("Transfer results require an application transaction.")
        TransferOperationModel.objects.filter(idempotency_key=key).update(
            source_balance_minor=source_balance.amount_minor,
            destination_balance_minor=destination_balance.amount_minor,
            currency=source_balance.currency,
        )


class DjangoSharedExpenseRepository(SharedExpenseRepository):
    def add(self, expense: SharedExpense) -> SharedExpense:
        if not connection.in_atomic_block:
            raise RuntimeError('Shared expenses require an application transaction.')
        SharedExpenseModel.objects.create(
            id=expense.id, title=expense.title, total_minor=expense.total.amount_minor,
            currency=expense.total.currency, payer_id=expense.payer,
        )
        ParticipantModel.objects.bulk_create([
            ParticipantModel(expense_id=expense.id, account_id=p.account.id, share_minor=p.share.amount_minor)
            for p in expense.participants
        ])
        return expense

    def get(self, expense_id: UUID) -> SharedExpense:
        try:
            row = SharedExpenseModel.objects.get(pk=expense_id)
        except SharedExpenseModel.DoesNotExist as exc:
            raise SharedExpenseNotFound('Shared expense does not exist.') from exc
        participants = tuple(
            Participant(account_entity(p.account), Share(Money(p.share_minor, row.currency)))
            for p in row.participants.select_related('account').all()
        )
        # The transfer debit is the authoritative amount and sender. Do not copy
        # either into a separate payment counter or depend on event delivery.
        operations = TransferOperationModel.objects.filter(shared_expense_id=expense_id).values('operation_id')
        payments = LedgerEntryModel.objects.filter(
            operation_id__in=operations, operation_type='transfer', amount_minor__lt=0,
            counterparty_id=row.payer_id, currency=row.currency,
        ).values('account_id').annotate(total=Sum('amount_minor'))
        return SharedExpense(row.id, row.title, Money(row.total_minor, row.currency), row.payer_id, participants).with_payments(
            {p['account_id']: -int(p['total']) for p in payments}
        )

    def list_expenses(self, account_id: UUID | None = None) -> list[SharedExpense]:
        rows = SharedExpenseModel.objects.all()
        if account_id is not None:
            rows = rows.filter(participants__account_id=account_id)
        return [self.get(i) for i in rows.values_list('id', flat=True)]

    def contexts_for(self, operation_ids: Iterable[UUID]) -> dict[UUID, tuple[UUID, str]]:
        return {
            operation_id: (expense_id, title)
            for operation_id, expense_id, title in TransferOperationModel.objects.filter(
                operation_id__in=operation_ids, shared_expense__isnull=False,
            ).values_list('operation_id', 'shared_expense_id', 'shared_expense__title')
        }
