from contextlib import nullcontext
from uuid import uuid4

import pytest

from src.application.commands import DepositCommand
from src.application.services import DepositService
from src.domain.entities import Account
from src.domain.errors import AccountNotFound
from src.domain.money import Money
from src.domain.repositories import AccountRepository, LedgerRepository


class FakeLedger(LedgerRepository):
    def __init__(self):
        self.entries = []

    def append(self, entries):
        self.entries.extend(entries)

    def entries_for(self, account_id):
        return [e for e in self.entries if e.account_id == account_id]

    def total_balance(self):
        return Money(sum(e.money.amount_minor for e in self.entries))


class FakeAccounts(AccountRepository):
    def __init__(self, ledger):
        self.accounts = {}
        self.ledger = ledger

    def add(self, account):
        self.accounts[account.id] = account
        return account

    def get(self, account_id):
        if account_id not in self.accounts:
            raise AccountNotFound()
        return self.accounts[account_id]

    def get_by_handle(self, handle):
        for account in self.accounts.values():
            if account.handle == handle:
                return account
        raise AccountNotFound()

    def list_user_accounts(self):
        return list(self.accounts.values())

    def handles_for(self, account_ids):
        return {account_id: self.accounts[account_id].handle for account_id in set(account_ids) if account_id in self.accounts}

    def balance_of(self, account_id):
        self.get(account_id)
        return Money(sum(e.money.amount_minor for e in self.ledger.entries_for(account_id)))


def service():
    ledger = FakeLedger()
    accounts = FakeAccounts(ledger)
    # Only replace Django's transaction boundary; no database access is permitted.
    return DepositService(accounts, ledger, atomic=nullcontext), accounts, ledger


def test_deposit_service_appends_both_entries():
    deposits, accounts, ledger = service()
    account = accounts.add(Account(uuid4(), "samuel", "Samuel"))
    result = deposits.deposit(DepositCommand(account.id, Money(501)))
    assert len(ledger.entries) == 2
    assert ledger.total_balance() == Money(0)
    assert accounts.balance_of(account.id) == Money(501)
    assert result.balance == Money(501)
    assert {e.operation_id for e in ledger.entries} == {result.operation_id}


def test_deposit_service_rejects_unknown_account():
    deposits, _, ledger = service()
    with pytest.raises(AccountNotFound):
        deposits.deposit(DepositCommand(uuid4(), Money(1)))
    assert ledger.entries == []
