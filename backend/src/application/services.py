from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import UUID, uuid4

from django.db import transaction

from src.domain.entities import Account, LedgerEntry
from src.domain.errors import DuplicateIdempotencyKey, IdempotencyConflict, InsufficientFunds, SameAccountTransfer
from src.domain.factories import LedgerEntryFactory
from src.domain.events import EventDispatcher, TransferCompleted
from src.domain.money import Money
from src.domain.repositories import AccountRepository, LedgerRepository, TransferOperationRepository, SharedExpenseRepository
from src.domain.shared_expenses import SharedExpense
from src.domain.split import EqualSplitStrategy
from .commands import CreateAccountCommand, DepositCommand, TransferCommand, CreateSharedExpenseCommand


@dataclass(frozen=True)
class AccountBalance:
    account: Account
    balance: Money


@dataclass(frozen=True)
class HistoryItem:
    entry: LedgerEntry
    counterparty_handle: str
    shared_expense_id: UUID | None = None
    shared_expense_title: str | None = None


@dataclass(frozen=True)
class DepositResult:
    operation_id: UUID
    balance: Money


class AccountService:
    def __init__(self, accounts: AccountRepository, ledger: LedgerRepository, *, new_id=uuid4, expenses: SharedExpenseRepository | None = None):
        self.accounts = accounts
        self.ledger = ledger
        self.new_id = new_id
        self.expenses = expenses

    def create(self, command: CreateAccountCommand) -> AccountBalance:
        with transaction.atomic():
            account = self.accounts.add(Account(self.new_id(), command.handle, command.display_name))
            return AccountBalance(account, self.accounts.balance_of(account.id))

    def list_accounts(self) -> list[AccountBalance]:
        return [
            AccountBalance(a, self.accounts.balance_of(a.id))
            for a in self.accounts.list_user_accounts()
        ]

    def get(self, account_id: UUID) -> AccountBalance:
        return AccountBalance(self.accounts.get(account_id), self.accounts.balance_of(account_id))

    def balance(self, account_id: UUID) -> Money:
        return self.accounts.balance_of(account_id)

    def history(self, account_id: UUID) -> list[HistoryItem]:
        self.accounts.get(account_id)
        entries = self.ledger.entries_for(account_id)
        handles = self.accounts.handles_for({e.counterparty_id for e in entries})
        transfer_ids = {e.operation_id for e in entries if e.operation_type == 'transfer'}
        contexts = self.expenses.contexts_for(transfer_ids) if self.expenses and transfer_ids else {}
        return [
            HistoryItem(e, handles[e.counterparty_id], *contexts.get(e.operation_id, (None, None)))
            for e in entries
        ]


class DepositService:
    def __init__(
        self, accounts: AccountRepository, ledger: LedgerRepository, *,
        atomic=transaction.atomic, new_id=uuid4, clock=lambda: datetime.now(timezone.utc),
    ):
        self.accounts = accounts
        self.ledger = ledger
        self.atomic = atomic
        self.new_id = new_id
        self.clock = clock

    def deposit(self, command: DepositCommand) -> DepositResult:
        with self.atomic():
            account = self.accounts.get(command.account_id)
            operation_id = self.new_id()
            entries = LedgerEntryFactory.for_deposit(
                account, command.amount, operation_id=operation_id, created_at=self.clock(),
            )
            self.ledger.append(entries)
            return DepositResult(operation_id, self.accounts.balance_of(account.id))


@dataclass(frozen=True)
class TransferResult:
    operation_id: UUID
    source_balance: Money
    destination_balance: Money
    replayed: bool = False
    shared_expense_id: UUID | None = None


class TransferService:
    def __init__(
        self, accounts: AccountRepository, ledger: LedgerRepository,
        operations: TransferOperationRepository, *, atomic=transaction.atomic,
        new_id=uuid4, clock=lambda: datetime.now(timezone.utc),
        expenses: SharedExpenseRepository | None = None,
        dispatcher: EventDispatcher | None = None, on_commit=transaction.on_commit,
    ):
        self.accounts = accounts
        self.ledger = ledger
        self.operations = operations
        self.atomic = atomic
        self.new_id = new_id
        self.clock = clock
        self.expenses = expenses
        self.dispatcher = dispatcher
        self.on_commit = on_commit

    def transfer(self, command: TransferCommand) -> TransferResult:
        request_data = [
            str(command.source_account_id), str(command.destination_account_id),
            command.amount.amount_minor, command.amount.currency,
        ]
        # Keep historical unlinked fingerprints stable across this additive change.
        if command.shared_expense_id is not None:
            request_data.append(str(command.shared_expense_id))
        fingerprint = sha256(json.dumps(request_data, separators=(",", ":")).encode("utf-8")).hexdigest()
        try:
            with self.atomic():
                if command.source_account_id == command.destination_account_id:
                    raise SameAccountTransfer("Source and destination must differ.")
                operation_id = self.new_id()
                # INSERT first: the unique constraint arbitrates concurrent retries.
                self.operations.claim(command.idempotency_key, fingerprint, operation_id)
                if command.shared_expense_id is not None:
                    if self.expenses is None:
                        raise RuntimeError('Shared expense repository is required for contextual transfers.')
                    expense = self.expenses.get(command.shared_expense_id)
                    expense.validate_transfer(command.source_account_id, command.destination_account_id)
                    self.operations.link_expense(operation_id, expense.id)
                accounts = {a.id: a for a in self.accounts.lock_for_update([
                    command.source_account_id, command.destination_account_id,
                ])}
                entries = LedgerEntryFactory.for_transfer(
                    accounts[command.source_account_id], accounts[command.destination_account_id],
                    command.amount, operation_id=operation_id, created_at=self.clock(),
                )
                # Never read funds before both account locks have been acquired.
                balance = self.accounts.balance_of(command.source_account_id)
                if balance.amount_minor < command.amount.amount_minor:
                    raise InsufficientFunds("Insufficient funds.")
                self.ledger.append(entries)
                result = TransferResult(
                    operation_id, self.accounts.balance_of(command.source_account_id),
                    self.accounts.balance_of(command.destination_account_id),
                    shared_expense_id=command.shared_expense_id,
                )
                self.operations.complete(command.idempotency_key, result.source_balance, result.destination_balance)
                if self.dispatcher is not None:
                    event = TransferCompleted(operation_id, command.shared_expense_id)
                    self.on_commit(lambda: self.dispatcher.publish(event), robust=True)
                return result
        except DuplicateIdempotencyKey:
            # The failed transaction must be rolled back before querying the winner.
            original = self.operations.get(command.idempotency_key)
            if original.request_fingerprint != fingerprint:
                raise IdempotencyConflict("Idempotency key was used for a different request.")
            return TransferResult(
                original.operation_id, original.source_balance, original.destination_balance, replayed=True,
                shared_expense_id=command.shared_expense_id,
            )


class SharedExpenseService:
    def __init__(
        self, accounts: AccountRepository, expenses: SharedExpenseRepository, *,
        atomic=transaction.atomic, new_id=uuid4,
    ):
        self.accounts = accounts
        self.expenses = expenses
        self.atomic = atomic
        self.new_id = new_id

    def create(self, command: CreateSharedExpenseCommand) -> SharedExpense:
        with self.atomic():
            accounts = [self.accounts.get(i) for i in sorted(command.participant_account_ids)]
            expense = SharedExpense.create(
                self.new_id(), command.title, command.total, command.payer_account_id,
                accounts, EqualSplitStrategy(),
            )
            return self.expenses.add(expense)

    def get(self, expense_id: UUID) -> SharedExpense:
        return self.expenses.get(expense_id)

    def list_expenses(self, account_id: UUID | None = None) -> list[SharedExpense]:
        if account_id is not None:
            self.accounts.get(account_id)
        return self.expenses.list_expenses(account_id)
