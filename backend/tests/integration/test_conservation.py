from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest
from django.db import DatabaseError, connection, transaction
from django.db.models import Sum
from rest_framework.test import APIClient

from src.application.commands import DepositCommand
from src.application.services import DepositService
from src.domain.entities import EXTERNAL_FUNDING_ID
from src.domain.money import Money
from src.domain.repositories import LedgerRepository
from src.infrastructure.persistence.models import AccountModel, LedgerEntryModel
from src.infrastructure.persistence.repositories import DjangoAccountRepository, DjangoLedgerRepository

pytestmark = pytest.mark.django_db


def deposit_sequence():
    client = APIClient()
    for index, amount in enumerate((1, 999, 5000000, 2**53 + 1)):
        account = client.post("/api/accounts/", {"handle": f"user_{index}", "display_name": "User"}, format="json").json()
        assert client.post(f"/api/accounts/{account['id']}/deposits/", {"amount_minor": amount, "currency": "COP"}, format="json").status_code == 201
    return 1 + 999 + 5000000 + 2**53 + 1


def test_global_ledger_sums_to_zero_after_deposits():
    deposit_sequence()
    assert LedgerEntryModel.objects.aggregate(total=Sum("amount_minor"))["total"] == 0
    operations = LedgerEntryModel.objects.values("operation_id", "currency").annotate(total=Sum("amount_minor"))
    assert len(operations) == 4
    assert all(op["total"] == 0 for op in operations)
    assert DjangoLedgerRepository().total_balance() == Money(0)


def test_external_funding_is_negative_and_hidden():
    total = deposit_sequence()
    funding = AccountModel.objects.get(pk=EXTERNAL_FUNDING_ID)
    assert funding.allows_negative_balance
    assert not AccountModel.objects.exclude(pk=EXTERNAL_FUNDING_ID).filter(allows_negative_balance=True).exists()
    assert DjangoAccountRepository().balance_of(EXTERNAL_FUNDING_ID) == Money(-total)
    accounts = APIClient().get("/api/accounts/").json()
    assert len(accounts) == 4
    assert all(a["id"] != str(EXTERNAL_FUNDING_ID) for a in accounts)


def test_ledger_entries_cannot_be_modified():
    deposit_sequence()
    repo = DjangoLedgerRepository()
    for cls in (LedgerRepository, DjangoLedgerRepository):
        assert not hasattr(cls, "update")
        assert not hasattr(cls, "delete")
    entry = repo.entries_for(EXTERNAL_FUNDING_ID)[0]
    with pytest.raises(FrozenInstanceError):
        entry.money = Money(0)
    row = LedgerEntryModel.objects.first()
    for sql in ("UPDATE persistence_ledgerentrymodel SET amount_minor = 0 WHERE id = %s", "DELETE FROM persistence_ledgerentrymodel WHERE id = %s"):
        with pytest.raises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(sql, [row.id])
    assert LedgerEntryModel.objects.count() == 8


def test_deposit_rolls_back_after_partial_write():
    account = AccountModel.objects.create(id=uuid4(), handle="rollback", display_name="Rollback")

    class FailingLedger(DjangoLedgerRepository):
        def append(self, entries):
            first = entries[0]
            LedgerEntryModel.objects.create(
                account_id=first.account_id, counterparty_id=first.counterparty_id,
                operation_id=first.operation_id, operation_type=first.operation_type,
                amount_minor=first.money.amount_minor, currency=first.money.currency,
                created_at=first.created_at,
            )
            raise DatabaseError("failure after debit")

    with pytest.raises(DatabaseError):
        DepositService(DjangoAccountRepository(), FailingLedger()).deposit(DepositCommand(account.id, Money(100)))
    assert LedgerEntryModel.objects.count() == 0
    assert DjangoAccountRepository().balance_of(account.id) == Money(0)


def test_repeated_deposits_are_distinct_balanced_operations():
    account = AccountModel.objects.create(id=uuid4(), handle="repeat", display_name="Repeat")
    service = DepositService(DjangoAccountRepository(), DjangoLedgerRepository())
    command = DepositCommand(account.id, Money(2**63 - 1))
    first = service.deposit(command)
    second = service.deposit(command)
    assert first.operation_id != second.operation_id
    assert second.balance == Money(2 * (2**63 - 1))
    assert LedgerEntryModel.objects.count() == 4
    assert DjangoLedgerRepository().total_balance() == Money(0)


def test_repository_batch_is_all_or_nothing():
    from dataclasses import replace
    from datetime import datetime, timezone
    from src.domain.factories import LedgerEntryFactory

    account = AccountModel.objects.create(id=uuid4(), handle="batch", display_name="Batch")
    entries = LedgerEntryFactory.for_deposit(
        DjangoAccountRepository().get(account.id), Money(100),
        operation_id=uuid4(), created_at=datetime.now(timezone.utc),
    )
    # The second row collides with the first PK. The first row must not survive.
    invalid_pair = (entries[0], replace(entries[1], id=entries[0].id))
    with pytest.raises(DatabaseError), transaction.atomic():
        DjangoLedgerRepository().append(invalid_pair)
    assert LedgerEntryModel.objects.count() == 0
