from uuid import uuid4

import pytest

from src.domain.entities import Account
from src.domain.errors import InvalidSharedExpense
from src.domain.money import Money
from src.domain.shared_expenses import SharedExpense
from src.domain.split import EqualSplitStrategy, SplitStrategy
from src.domain.events import EventDispatcher, TransferCompleted


def people():
    return [Account(uuid4(), 'alice', 'Alice'), Account(uuid4(), 'bobby', 'Bob')]


def test_shared_expense_uses_strategy_without_branching():
    accounts = people()

    class Stub(SplitStrategy):
        def split(self, total, participant_ids):
            assert total == Money(100)
            assert set(participant_ids) == {a.id for a in accounts}
            return {accounts[0].id: Money(40), accounts[1].id: Money(60)}

    expense = SharedExpense.create(uuid4(), 'Dinner', Money(100), accounts[0].id, accounts, Stub())
    assert [p.share.amount_minor for p in expense.participants] == [40, 60]


def test_payer_share_is_settled_at_creation():
    accounts = people()
    expense = SharedExpense.create(uuid4(), 'Dinner', Money(100), accounts[0].id, accounts, EqualSplitStrategy())
    payer, other = expense.participants
    assert payer.settled and payer.paid_minor == 50 and payer.outstanding_minor == 0
    assert other.paid_minor == 0 and other.outstanding_minor == 50
    assert expense.outstanding_total_minor == 50 and not expense.settled


@pytest.mark.parametrize('shares', [[0, 100], [40, 59], [40, 61]])
def test_expense_validates_strategy_result(shares):
    accounts = people()

    class Invalid(SplitStrategy):
        def split(self, total, participant_ids):
            return {a.id: Money(n) for a, n in zip(accounts, shares)}

    with pytest.raises(InvalidSharedExpense):
        SharedExpense.create(uuid4(), 'Dinner', Money(100), accounts[0].id, accounts, Invalid())


def test_failing_handler_does_not_prevent_other_handlers(caplog):
    dispatcher = EventDispatcher()
    seen = []

    def fail(event):
        raise RuntimeError('failed observer')

    dispatcher.subscribe(TransferCompleted, fail)
    dispatcher.subscribe(TransferCompleted, seen.append)
    event = TransferCompleted(uuid4(), uuid4())
    dispatcher.publish(event)
    assert seen == [event] and 'failed observer' in caplog.text
