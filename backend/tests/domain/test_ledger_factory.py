from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.entities import Account, EXTERNAL_FUNDING_ID
from src.domain.errors import InvalidDeposit
from src.domain.factories import LedgerEntryFactory
from src.domain.money import Money


def make_pair(amount):
    return LedgerEntryFactory.for_deposit(
        Account(uuid4(), "samuel", "Samuel"), Money(amount),
        operation_id=uuid4(), created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_deposit_factory_returns_balanced_pair():
    entries = make_pair(5000000)
    assert len(entries) == 2
    assert sum(e.money.amount_minor for e in entries) == 0
    assert len({e.operation_id for e in entries}) == 1
    assert {e.operation_type for e in entries} == {"deposit"}
    assert {e.money.currency for e in entries} == {"COP"}
    debit, credit = entries
    assert debit.account_id == EXTERNAL_FUNDING_ID
    assert debit.money == Money(-5000000)
    assert credit.money == Money(5000000)
    assert credit.counterparty_id == debit.account_id
    assert debit.counterparty_id == credit.account_id


@pytest.mark.parametrize("amount", [0, -1])
def test_deposit_factory_rejects_non_positive_amount(amount):
    with pytest.raises(InvalidDeposit):
        make_pair(amount)


def test_funding_account_cannot_be_deposit_target():
    with pytest.raises(InvalidDeposit):
        LedgerEntryFactory.for_deposit(
            Account(EXTERNAL_FUNDING_ID, "EXTERNAL_FUNDING", "External funding", True),
            Money(1), operation_id=uuid4(), created_at=datetime.now(timezone.utc),
        )
