from collections.abc import Iterable, Sequence
from uuid import UUID

from django.db import IntegrityError, connection
from django.db.models import Sum

from src.domain.entities import Account, EXTERNAL_FUNDING_ID, LedgerEntry, TransferOperation
from src.domain.errors import AccountNotFound, DuplicateHandle, DuplicateIdempotencyKey
from src.domain.money import Money
from src.domain.repositories import AccountRepository, LedgerRepository, TransferOperationRepository
from .models import AccountModel, LedgerEntryModel, TransferOperationModel


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
