from contextlib import nullcontext
from uuid import uuid4

import pytest

from src.application.commands import TransferCommand
from src.application.services import TransferService
from src.domain.entities import Account
from src.domain.errors import InsufficientFunds, SameAccountTransfer
from src.domain.money import Money


class Accounts:
    def __init__(self, balance):
        self.source = Account(uuid4(), "source", "Source")
        self.destination = Account(uuid4(), "destination", "Destination")
        self.balance = balance
        self.calls = []

    def lock_for_update(self, ids):
        self.calls.append(("lock", ids))
        return sorted([self.source, self.destination], key=lambda a: a.id)

    def balance_of(self, account_id):
        self.calls.append(("balance", account_id))
        return Money(self.balance if account_id == self.source.id else 0)


class Ledger:
    def __init__(self):
        self.entries = []

    def append(self, entries):
        self.entries.extend(entries)


class Operations:
    def __init__(self):
        self.claims = []
        self.results = []

    def claim(self, *args):
        self.claims.append(args)

    def complete(self, *args):
        self.results.append(args)


def setup(balance=100):
    accounts, ledger, operations = Accounts(balance), Ledger(), Operations()
    service = TransferService(accounts, ledger, operations, atomic=nullcontext)
    command = TransferCommand(accounts.source.id, accounts.destination.id, Money(100), "test-key")
    return service, command, accounts, ledger, operations


def test_transfer_service_locks_before_reading_balance():
    service, command, accounts, ledger, operations = setup()
    service.transfer(command)
    assert accounts.calls[0][0] == "lock"
    assert set(accounts.calls[0][1]) == {command.source_account_id, command.destination_account_id}
    assert accounts.calls[1] == ("balance", command.source_account_id)
    assert len(ledger.entries) == 2
    assert len(operations.claims) == len(operations.results) == 1


def test_transfer_service_rejects_insufficient_funds():
    service, command, accounts, ledger, operations = setup(99)
    with pytest.raises(InsufficientFunds, match="Insufficient funds"):
        service.transfer(command)
    assert ledger.entries == []
    assert operations.results == []


def test_same_account_is_rejected_before_claim_or_lock():
    service, command, accounts, ledger, operations = setup()
    with pytest.raises(SameAccountTransfer):
        service.transfer(TransferCommand(command.source_account_id, command.source_account_id, Money(1), "test-key"))
    assert accounts.calls == operations.claims == ledger.entries == []
