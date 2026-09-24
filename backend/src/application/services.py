from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from django.db import transaction

from src.domain.entities import Account, LedgerEntry
from src.domain.factories import LedgerEntryFactory
from src.domain.money import Money
from src.domain.repositories import AccountRepository, LedgerRepository
from .commands import CreateAccountCommand, DepositCommand


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
