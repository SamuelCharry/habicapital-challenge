from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import UUID, uuid4

from django.db import transaction

from src.domain.entities import Account, LedgerEntry
from src.domain.errors import DuplicateIdempotencyKey, IdempotencyConflict, InsufficientFunds, SameAccountTransfer
from src.domain.factories import LedgerEntryFactory
from src.domain.money import Money
from src.domain.repositories import AccountRepository, LedgerRepository, TransferOperationRepository
from .commands import CreateAccountCommand, DepositCommand, TransferCommand


@dataclass(frozen=True)
class AccountBalance:
    account: Account
    balance: Money


@dataclass(frozen=True)
class HistoryItem:
    entry: LedgerEntry
    counterparty_handle: str


@dataclass(frozen=True)
class DepositResult:
    operation_id: UUID
    balance: Money


class AccountService:
    def __init__(self, accounts: AccountRepository, ledger: LedgerRepository, *, new_id=uuid4):
        self.accounts = accounts
        self.ledger = ledger
        self.new_id = new_id

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
        return [
            HistoryItem(e, handles[e.counterparty_id])
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


class TransferService:
    def __init__(
        self, accounts: AccountRepository, ledger: LedgerRepository,
        operations: TransferOperationRepository, *, atomic=transaction.atomic,
        new_id=uuid4, clock=lambda: datetime.now(timezone.utc),
    ):
        self.accounts = accounts
        self.ledger = ledger
        self.operations = operations
        self.atomic = atomic
        self.new_id = new_id
        self.clock = clock

    def transfer(self, command: TransferCommand) -> TransferResult:
        fingerprint = sha256(json.dumps([
            str(command.source_account_id), str(command.destination_account_id),
            command.amount.amount_minor, command.amount.currency,
        ], separators=(",", ":")).encode("utf-8")).hexdigest()
        try:
            with self.atomic():
                if command.source_account_id == command.destination_account_id:
                    raise SameAccountTransfer("Source and destination must differ.")
                operation_id = self.new_id()
                # INSERT first: the unique constraint arbitrates concurrent retries.
                self.operations.claim(command.idempotency_key, fingerprint, operation_id)
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
                )
                self.operations.complete(command.idempotency_key, result.source_balance, result.destination_balance)
                return result
        except DuplicateIdempotencyKey:
            # The failed transaction must be rolled back before querying the winner.
            original = self.operations.get(command.idempotency_key)
            if original.request_fingerprint != fingerprint:
                raise IdempotencyConflict("Idempotency key was used for a different request.")
            return TransferResult(
                original.operation_id, original.source_balance, original.destination_balance, replayed=True,
            )
