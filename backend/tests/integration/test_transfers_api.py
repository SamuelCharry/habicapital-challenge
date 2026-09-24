from uuid import UUID, uuid4

import pytest
from django.db import DatabaseError, IntegrityError, connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from src.application.commands import TransferCommand
from src.application.services import TransferService
from src.domain.entities import EXTERNAL_FUNDING_ID
from src.domain.money import Money
from src.infrastructure.persistence.models import LedgerEntryModel, TransferOperationModel
from src.infrastructure.persistence.repositories import DjangoAccountRepository, DjangoLedgerRepository, DjangoTransferOperationRepository

pytestmark = pytest.mark.django_db


def account(handle):
    response = APIClient().post("/api/accounts/", {"handle": handle, "display_name": handle}, format="json")
    assert response.status_code == 201
    return response.json()["id"]


def deposit(account_id, amount):
    response = APIClient().post(f"/api/accounts/{account_id}/deposits/", {"amount_minor": amount, "currency": "COP"}, format="json")
    assert response.status_code == 201


def payload(source, destination, **changes):
    return dict(source_account_id=str(source), destination_account_id=str(destination), amount_minor=100, currency="COP", idempotency_key="transfer-key") | changes


def post(data):
    return APIClient().post("/api/transfers/", data, format="json")


def funded_pair(amount=100):
    source, destination = account("source"), account("destination")
    deposit(source, amount)
    return source, destination


def test_transfer_moves_money_and_both_balances_change():
    source, destination = funded_pair(2**53 + 1)
    response = post(payload(source, destination, amount_minor=2**53 + 1))
    assert response.status_code == 201
    assert response.json() == dict(operation_id=response.json()["operation_id"], source_balance_minor=0, destination_balance_minor=2**53 + 1, currency="COP", replayed=False, shared_expense_id=None)
    repo = DjangoAccountRepository()
    assert repo.balance_of(UUID(source)) == Money(0)
    assert repo.balance_of(UUID(destination)) == Money(2**53 + 1)
    entries = LedgerEntryModel.objects.filter(operation_id=response.json()["operation_id"])
    assert entries.count() == 2
    assert sum(entries.values_list("amount_minor", flat=True)) == 0


def test_transfer_rejects_insufficient_funds_and_writes_nothing():
    source, destination = funded_pair(99)
    before = list(LedgerEntryModel.objects.values())
    response = post(payload(source, destination))
    assert response.status_code == 422
    assert response.json() == {"detail": "Insufficient funds."}
    assert list(LedgerEntryModel.objects.values()) == before
    assert not TransferOperationModel.objects.exists()
    deposit(source, 1)
    assert post(payload(source, destination)).status_code == 201


def test_transfer_rejects_same_account():
    source, _ = funded_pair()
    with CaptureQueriesContext(connection) as queries:
        assert post(payload(source, source)).status_code == 400
    assert not any("FOR UPDATE" in q["sql"] for q in queries)
    assert not TransferOperationModel.objects.exists()


@pytest.mark.parametrize("amount", [0, -1])
def test_transfer_rejects_zero_and_negative(amount):
    source, destination = funded_pair()
    assert post(payload(source, destination, amount_minor=amount)).status_code == 400
    assert not TransferOperationModel.objects.exists()
    assert LedgerEntryModel.objects.count() == 2


@pytest.mark.parametrize("side", ["source_account_id", "destination_account_id"])
def test_transfer_rejects_unknown_source_and_destination(side):
    source, destination = funded_pair()
    assert post(payload(source, destination, **{side: str(uuid4())})).status_code == 404
    assert not TransferOperationModel.objects.exists()
    assert LedgerEntryModel.objects.count() == 2


@pytest.mark.parametrize("side", ["source_account_id", "destination_account_id"])
def test_transfer_rejects_external_funding_as_either_party(side):
    source, destination = funded_pair()
    assert post(payload(source, destination, **{side: str(EXTERNAL_FUNDING_ID)})).status_code == 400
    assert not TransferOperationModel.objects.exists()
    assert LedgerEntryModel.objects.count() == 2


def test_replayed_idempotency_key_returns_original_result():
    source, destination = funded_pair()
    data = payload(source, destination)
    original = post(data)
    assert original.status_code == 201
    deposit(source, 900)
    deposit(destination, 700)
    replay = post(data)
    assert replay.status_code == 200
    assert replay.json() == original.json() | {"replayed": True}
    assert TransferOperationModel.objects.count() == 1
    assert LedgerEntryModel.objects.filter(operation_type="transfer").count() == 2


@pytest.mark.parametrize("change", [{"amount_minor": 1}, {"source_account_id": str(uuid4())}, {"destination_account_id": str(uuid4())}])
def test_same_key_different_payload_returns_409(change):
    source, destination = funded_pair()
    data = payload(source, destination)
    assert post(data).status_code == 201
    assert post(data | change).status_code == 409
    assert TransferOperationModel.objects.count() == 1
    assert LedgerEntryModel.objects.filter(operation_type="transfer").count() == 2


def test_rollback_after_injected_failure_leaves_no_entries():
    source, destination = funded_pair()

    class FailingLedger(DjangoLedgerRepository):
        def append(self, entries):
            super().append(entries[:1])
            raise DatabaseError("failure after debit")

    service = TransferService(DjangoAccountRepository(), FailingLedger(), DjangoTransferOperationRepository())
    with pytest.raises(DatabaseError, match="failure after debit"):
        service.transfer(TransferCommand(UUID(source), UUID(destination), Money(100), "transfer-key"))
    assert LedgerEntryModel.objects.count() == 2
    assert not LedgerEntryModel.objects.filter(operation_type="transfer").exists()
    assert not TransferOperationModel.objects.exists()
    assert post(payload(source, destination)).status_code == 201


@pytest.mark.parametrize("key", [None, "", "short", "x" * 129, 12345678])
def test_invalid_idempotency_key(key):
    data = payload(uuid4(), uuid4())
    if key is None:
        del data["idempotency_key"]
    else:
        data["idempotency_key"] = key
    assert post(data).status_code == 400
    assert not TransferOperationModel.objects.exists()


@pytest.mark.parametrize("change", [{"amount_minor": True}, {"amount_minor": 1.0}, {"amount_minor": "100"}, {"amount_minor": 2**63}, {"currency": "USD"}, {"source_account_id": "bad"}])
def test_invalid_transfer_shape(change):
    assert post(payload(uuid4(), uuid4()) | change).status_code == 400
    assert not TransferOperationModel.objects.exists()


def test_repository_locks_in_ascending_uuid_order():
    source, destination = funded_pair()
    with CaptureQueriesContext(connection) as queries:
        locked = DjangoAccountRepository().lock_for_update([UUID(destination), UUID(source)])
    assert [a.id for a in locked] == sorted([UUID(source), UUID(destination)])
    sql = [q["sql"] for q in queries if "FOR UPDATE" in q["sql"]]
    assert len(sql) == 1
    assert 'ORDER BY "persistence_accountmodel"."id" ASC' in sql[0]


def test_response_balances_above_bigint_replay_exactly():
    source, destination = funded_pair(2**63 - 1)
    deposit(source, 2**63 - 1)
    deposit(destination, 2**63 - 1)
    data = payload(source, destination, amount_minor=1)
    original = post(data)
    assert original.status_code == 201
    assert original.json()["source_balance_minor"] == 2 * (2**63 - 1) - 1
    assert original.json()["destination_balance_minor"] == 2**63
    replay = post(data)
    assert replay.status_code == 200
    assert replay.json() == original.json() | {"replayed": True}


def test_failure_storing_result_rolls_back_both_entries_and_claim():
    source, destination = funded_pair()

    class FailingOperations(DjangoTransferOperationRepository):
        def complete(self, *args):
            super().complete(*args)
            raise DatabaseError("failure storing response")

    service = TransferService(DjangoAccountRepository(), DjangoLedgerRepository(), FailingOperations())
    with pytest.raises(DatabaseError, match="failure storing response"):
        service.transfer(TransferCommand(UUID(source), UUID(destination), Money(100), "transfer-key"))
    assert LedgerEntryModel.objects.count() == 2
    assert not TransferOperationModel.objects.exists()
    assert post(payload(source, destination)).status_code == 201


def test_unrelated_integrity_error_is_not_treated_as_replay():
    source, destination = funded_pair(200)
    original = post(payload(source, destination))
    assert original.status_code == 201
    operation_id = UUID(original.json()["operation_id"])
    service = TransferService(
        DjangoAccountRepository(), DjangoLedgerRepository(), DjangoTransferOperationRepository(),
        new_id=lambda: operation_id,
    )
    with pytest.raises(IntegrityError):
        service.transfer(TransferCommand(UUID(source), UUID(destination), Money(100), "another-key"))
    assert TransferOperationModel.objects.count() == 1
    assert LedgerEntryModel.objects.count() == 4
    assert post(payload(source, destination, idempotency_key="another-key")).status_code == 201


def test_claim_is_inserted_before_any_idempotency_lookup():
    source, destination = funded_pair()
    data = payload(source, destination)
    for expected_status in (201, 200):
        with CaptureQueriesContext(connection) as queries:
            assert post(data).status_code == expected_status
        claim_queries = [q["sql"] for q in queries if '"persistence_transferoperationmodel"' in q["sql"]]
        assert claim_queries[0].startswith("INSERT INTO")
