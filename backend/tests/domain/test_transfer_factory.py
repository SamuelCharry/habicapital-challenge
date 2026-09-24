from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.entities import Account, EXTERNAL_FUNDING_ID
from src.domain.errors import DomainError, SameAccountTransfer
from src.domain.factories import LedgerEntryFactory
from src.domain.money import Money


def pair(amount=101, source=None, destination=None):
    return LedgerEntryFactory.for_transfer(
        source or Account(uuid4(), "source", "Source"),
        destination or Account(uuid4(), "destination", "Destination"), amount,
        operation_id=uuid4(), created_at=datetime.now(timezone.utc),
    )


def test_transfer_factory_returns_balanced_pair():
    debit, credit = pair(Money(2**53 + 1))
    assert debit.money.amount_minor == -(2**53 + 1)
    assert credit.money.amount_minor == 2**53 + 1
    assert debit.money.add(credit.money) == Money(0)
    assert debit.operation_id == credit.operation_id
    assert debit.id != credit.id
    assert debit.account_id == credit.counterparty_id
    assert credit.account_id == debit.counterparty_id
    assert debit.operation_type == credit.operation_type == "transfer"


@pytest.mark.parametrize("amount", [Money(0), Money(-1), Money(2**63), 1.5, "100", None])
def test_transfer_factory_rejects_non_positive_amount(amount):
    with pytest.raises(DomainError):
        pair(amount)


def test_transfer_factory_rejects_same_account():
    account = Account(uuid4(), "same", "Same")
    with pytest.raises(SameAccountTransfer):
        pair(Money(1), account, account)


@pytest.mark.parametrize("side", ["source", "destination"])
def test_transfer_factory_rejects_funding(side):
    funding = Account(EXTERNAL_FUNDING_ID, "EXTERNAL_FUNDING", "Funding", True)
    with pytest.raises(DomainError):
        pair(Money(1), **{side: funding})
