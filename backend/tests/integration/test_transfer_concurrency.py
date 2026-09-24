from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID

import pytest
from rest_framework.test import APIClient
from django.db import close_old_connections, connections
from django.db.models import Count, Sum

from src.domain.entities import EXTERNAL_FUNDING_ID
from src.infrastructure.persistence.models import AccountModel, LedgerEntryModel, TransferOperationModel
from src.infrastructure.persistence.repositories import DjangoAccountRepository
from tests.integration.test_transfers_api import account, deposit, funded_pair, payload, post

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def funding_account():
    # Transactional tests flush seed data between tests.
    AccountModel.objects.get_or_create(
        pk=EXTERNAL_FUNDING_ID,
        defaults=dict(handle="EXTERNAL_FUNDING", display_name="Funding", allows_negative_balance=True),
    )


def concurrently(jobs):
    barrier = Barrier(len(jobs))

    def worker(job):
        close_old_connections()
        try:
            with connections["default"].cursor() as cursor:
                cursor.execute("SET statement_timeout = '15s'")
                cursor.execute("SET lock_timeout = '10s'")
                cursor.execute("SELECT pg_backend_pid()")
                pid = cursor.fetchone()[0]
            barrier.wait(timeout=15)
            return pid, job()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=len(jobs)) as executor:
        futures = [executor.submit(worker, job) for job in jobs]
        results = [future.result(timeout=30) for future in futures]
    assert len({pid for pid, _ in results}) == len(jobs)
    return [result for _, result in results]


def assert_conservation():
    totals = LedgerEntryModel.objects.values("currency").annotate(total=Sum("amount_minor"))
    assert list(totals) == [{"currency": "COP", "total": 0}]
    operations = LedgerEntryModel.objects.values("operation_id", "currency").annotate(total=Sum("amount_minor"), count=Count("id"))
    assert all(op["total"] == 0 and op["count"] == 2 for op in operations)
    repo = DjangoAccountRepository()
    assert all(repo.balance_of(a.id).amount_minor >= 0 for a in AccountModel.objects.exclude(pk=EXTERNAL_FUNDING_ID))


def test_concurrent_duplicate_idempotency_key_creates_one_transfer():
    source, destination = funded_pair()
    data = payload(source, destination)
    responses = concurrently([lambda: post(data) for _ in range(8)])
    assert sorted(r.status_code for r in responses) == [200] * 7 + [201]
    first = next(r.json() for r in responses if r.status_code == 201)
    assert all(r.json() == first | {"replayed": r.status_code == 200} for r in responses)
    assert TransferOperationModel.objects.count() == 1
    assert LedgerEntryModel.objects.filter(operation_type="transfer").count() == 2
    assert_conservation()


def test_concurrent_transfers_cannot_overspend():
    source, destination = funded_pair()
    other = account("other")
    responses = concurrently([
        lambda: post(payload(source, destination, idempotency_key="overspend-one")),
        lambda: post(payload(source, other, idempotency_key="overspend-two")),
    ])
    assert sorted(r.status_code for r in responses) == [201, 422]
    assert DjangoAccountRepository().balance_of(UUID(source)).amount_minor == 0
    assert TransferOperationModel.objects.count() == 1
    assert LedgerEntryModel.objects.filter(operation_type="transfer").count() == 2
    assert_conservation()


def test_concurrent_key_reuse_with_different_payload_returns_conflict():
    source, destination = funded_pair(1000)
    responses = concurrently([
        lambda: post(payload(source, destination, amount_minor=100)),
        lambda: post(payload(source, destination, amount_minor=200)),
    ])
    assert sorted(r.status_code for r in responses) == [201, 409]
    assert TransferOperationModel.objects.count() == 1
    assert LedgerEntryModel.objects.filter(operation_type="transfer").count() == 2
    assert_conservation()


def test_opposite_transfers_do_not_deadlock():
    source, destination = funded_pair(1000)
    deposit(destination, 1000)
    for index in range(20):
        responses = concurrently([
            lambda: post(payload(source, destination, idempotency_key=f"forward-{index}")),
            lambda: post(payload(destination, source, idempotency_key=f"reverse-{index}")),
        ])
        assert [r.status_code for r in responses] == [201, 201]
    repo = DjangoAccountRepository()
    assert repo.balance_of(UUID(source)).amount_minor == repo.balance_of(UUID(destination)).amount_minor == 1000
    assert TransferOperationModel.objects.count() == 40
    assert_conservation()


def test_global_conservation_after_concurrent_load():
    ids = [account(f"load_{i}") for i in range(4)]
    for account_id in ids:
        deposit(account_id, 10000)

    def load(index):
        source, destination = ids[index % 4], ids[(index + 1) % 4]
        for iteration in range(10):
            deposit(source, 17)
            data = payload(source, destination, amount_minor=31, idempotency_key=f"load-{index}-{iteration}")
            assert post(data).status_code == 201
            assert post(data).status_code == 200

    concurrently([lambda i=i: load(i) for i in range(8)])
    assert TransferOperationModel.objects.count() == 80
    assert_conservation()


def test_concurrent_deposits_and_transfers_keep_the_balance_exact():
    """Deposits and transfers touch the same account row through different
    operations. Interleaving them must not lose or invent a peso."""
    source, destination = funded_pair(20000)
    start = DjangoAccountRepository().balance_of(UUID(source)).amount_minor

    def make_deposit():
        return APIClient().post(
            f"/api/accounts/{source}/deposits/",
            {"amount_minor": 1000, "currency": "COP"}, format="json",
        ).status_code

    def make_transfer(index):
        return post(payload(source, destination, amount_minor=1000,
                            idempotency_key=f"mixed-race-{index:04d}")).status_code

    jobs = [make_deposit if i % 2 else (lambda i=i: make_transfer(i)) for i in range(20)]
    statuses = concurrently(jobs)

    deposits = sum(1 for i, code in enumerate(statuses) if i % 2 and code == 201)
    transfers = sum(1 for i, code in enumerate(statuses) if i % 2 == 0 and code == 201)
    assert deposits + transfers == 20, statuses
    balance = DjangoAccountRepository().balance_of(UUID(source)).amount_minor
    assert balance == start + deposits * 1000 - transfers * 1000
    assert_conservation()
