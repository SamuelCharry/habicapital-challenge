from uuid import uuid4

import pytest
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from src.infrastructure.persistence.models import AccountModel, LedgerEntryModel

pytestmark = pytest.mark.django_db


def create_account(handle="samuel"):
    response = APIClient().post("/api/accounts/", {"handle": handle, "display_name": "Samuel"}, format="json")
    assert response.status_code == 201
    return response.json()


def test_create_account_and_read_balance():
    account = create_account()
    assert account["balance_minor"] == 0
    assert account["currency"] == "COP"
    assert APIClient().get(f"/api/accounts/{account['id']}/").json() == account
    assert APIClient().get(f"/api/accounts/{account['id']}/balance/").json() == {"balance_minor": 0, "currency": "COP"}


def test_duplicate_handle_is_rejected():
    create_account()
    response = APIClient().post("/api/accounts/", {"handle": "samuel", "display_name": "Other"}, format="json")
    assert response.status_code == 400
    with pytest.raises(IntegrityError), transaction.atomic():
        AccountModel.objects.create(id=uuid4(), handle="samuel", display_name="Other")


def test_deposit_increases_balance_and_history():
    account = create_account()
    url = f"/api/accounts/{account['id']}/"
    amount = 2**53 + 1
    response = APIClient().post(url + "deposits/", {"amount_minor": amount, "currency": "COP"}, format="json")
    assert response.status_code == 201
    assert response.json()["balance_minor"] == amount
    assert type(response.json()["balance_minor"]) is int
    history = APIClient().get(url + "history/").json()
    assert len(history) == 1
    assert history[0]["amount_minor"] == amount
    assert history[0]["operation_id"] == response.json()["operation_id"]
    assert history[0]["operation_type"] == "deposit"
    assert history[0]["counterparty_handle"] == "EXTERNAL_FUNDING"
    assert history[0]["created_at"]


def test_account_history_has_bounded_query_count():
    account = create_account()
    client = APIClient()
    url = f"/api/accounts/{account['id']}/"
    amounts = list(range(1, 9))
    for amount in amounts:
        response = client.post(url + "deposits/", {"amount_minor": amount, "currency": "COP"}, format="json")
        assert response.status_code == 201

    with CaptureQueriesContext(connection) as queries:
        response = client.get(url + "history/")

    assert response.status_code == 200
    history = response.json()
    assert [entry["amount_minor"] for entry in history] == amounts
    assert all(entry["counterparty_handle"] == "EXTERNAL_FUNDING" for entry in history)
    # Account existence, ledger entries, and one batch of counterparty handles.
    assert len(queries) <= 3, queries.captured_queries


@pytest.mark.parametrize("amount", [0, -1])
def test_deposit_rejects_zero_and_negative(amount):
    account = create_account()
    response = APIClient().post(f"/api/accounts/{account['id']}/deposits/", {"amount_minor": amount, "currency": "COP"}, format="json")
    assert response.status_code == 400
    assert LedgerEntryModel.objects.count() == 0


@pytest.mark.parametrize("literal", ['1.0', '1.5', '1e2', 'true', '"100"', 'null', 'NaN', 'Infinity', str(2**63)])
def test_deposit_rejects_non_integer_or_out_of_range_json(literal):
    account = create_account()
    response = APIClient().post(f"/api/accounts/{account['id']}/deposits/", data='{"amount_minor":' + literal + ',"currency":"COP"}', content_type="application/json")
    assert response.status_code == 400
    assert LedgerEntryModel.objects.count() == 0


@pytest.mark.parametrize("payload", [{}, {"amount_minor": 1}, {"amount_minor": 1, "currency": "USD"}])
def test_deposit_invalid_shape(payload):
    account = create_account()
    assert APIClient().post(f"/api/accounts/{account['id']}/deposits/", payload, format="json").status_code == 400


@pytest.mark.parametrize("handle", ["ABCD", "ab", "a" * 21, "bad-handle", " samuel "])
def test_invalid_handles(handle):
    assert APIClient().post("/api/accounts/", {"handle": handle, "display_name": "Name"}, format="json").status_code == 400


def test_unknown_account_routes():
    url = f"/api/accounts/{uuid4()}/"
    for suffix in ("", "balance/", "history/"):
        assert APIClient().get(url + suffix).status_code == 404
    assert APIClient().post(url + "deposits/", {"amount_minor": 1, "currency": "COP"}, format="json").status_code == 404
