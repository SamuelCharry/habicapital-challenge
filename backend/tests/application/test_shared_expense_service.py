from contextlib import nullcontext
from uuid import uuid4

from src.application.commands import CreateSharedExpenseCommand
from src.application.event_handlers import SharedExpenseUpdater
from src.application.services import SharedExpenseService
from src.domain.entities import Account
from src.domain.events import TransferCompleted
from src.domain.money import Money


class Accounts:
    def __init__(self):
        self.people = [Account(uuid4(), 'alice', 'Alice'), Account(uuid4(), 'bobby', 'Bob')]

    def get(self, account_id):
        return next(a for a in self.people if a.id == account_id)


class Expenses:
    def add(self, expense):
        self.expense = expense
        return expense

    def get(self, expense_id):
        assert expense_id == self.expense.id
        return self.expense


def setup():
    accounts, expenses = Accounts(), Expenses()
    service = SharedExpenseService(accounts, expenses, atomic=nullcontext)
    command = CreateSharedExpenseCommand('Dinner', Money(100), accounts.people[0].id, tuple(a.id for a in accounts.people))
    return service, command, expenses


def test_create_shared_expense_writes_no_ledger_entries():
    service, command, expenses = setup()
    # There is deliberately no ledger or transfer dependency available to this use case.
    result = service.create(command)
    assert result == expenses.expense
    assert result.outstanding_total_minor == 50


def test_shared_expense_updater_marks_participant_paid():
    service, command, expenses = setup()
    expense = service.create(command)
    # Repository reads derive payments from committed transfers, not handler writes.
    expenses.expense = expense.with_payments({command.participant_account_ids[1]: 50})
    updated = SharedExpenseUpdater(expenses)(TransferCompleted(uuid4(), expense.id))
    assert updated.settled
    assert next(p for p in updated.participants if p.account.id == command.participant_account_ids[1]).paid_minor == 50
