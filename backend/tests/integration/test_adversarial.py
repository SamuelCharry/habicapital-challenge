"""Regression tests for the adversarial pass.

Each test here exists because the behaviour was probed by hand against a
running server first. They are the evidence behind the README's claim that
the system does not lose a peso.
"""

from uuid import uuid4

import pytest
from django.db.models import Sum
from rest_framework.test import APIClient

from src.domain.entities import EXTERNAL_FUNDING_ID
from src.infrastructure.persistence.models import AccountModel, LedgerEntryModel

pytestmark = pytest.mark.django_db

FUNDING = str(EXTERNAL_FUNDING_ID)


def account(client, handle, amount_minor=0):
    created = client.post(
        '/api/accounts/', {'handle': handle, 'display_name': handle.title()}, format='json'
    ).json()
    if amount_minor:
        client.post(
            f'/api/accounts/{created["id"]}/deposits/',
            {'amount_minor': amount_minor, 'currency': 'COP'},
            format='json',
        )
    return created['id']


def ledger_total():
    return LedgerEntryModel.objects.aggregate(total=Sum('amount_minor'))['total'] or 0


def test_sql_injection_in_text_fields_is_stored_as_data():
    """Parameterised queries mean a payload like this is text, not SQL."""
    client = APIClient()
    payer = account(client, 'inject_a', 1_000_000)
    other = account(client, 'inject_b')
    before = LedgerEntryModel.objects.count()

    hostile = "'; DELETE FROM persistence_ledgerentrymodel; --"
    created = client.post(
        '/api/shared-expenses/',
        {
            'title': hostile,
            'total_minor': 1000,
            'currency': 'COP',
            'payer_account_id': payer,
            'participant_account_ids': [payer, other],
            'split': 'equal',
        },
        format='json',
    )

    assert created.status_code == 201
    assert created.json()['title'] == hostile
    assert LedgerEntryModel.objects.count() == before
    assert ledger_total() == 0


def test_hostile_handles_are_rejected_by_the_pattern():
    client = APIClient()
    for handle in ["a'; DROP TABLE persistence_accountmodel;--", '🔥🔥🔥', 'MAYUSCULAS', 'ab', 'x' * 21]:
        response = client.post(
            '/api/accounts/', {'handle': handle, 'display_name': 'x'}, format='json'
        )
        assert response.status_code == 400, handle
    assert AccountModel.objects.exclude(pk=EXTERNAL_FUNDING_ID).count() == 0


def test_unmatched_api_path_answers_json_not_html():
    response = APIClient().get('/api/accounts/not-a-uuid/balance/')
    assert response.status_code == 404
    assert response['Content-Type'].startswith('application/json')
    assert response.json() == {'detail': 'Not found.'}


def test_funding_account_cannot_be_either_side_of_a_transfer():
    client = APIClient()
    user = account(client, 'party', 1_000_000)
    for source, destination in ((user, FUNDING), (FUNDING, user)):
        response = client.post(
            '/api/transfers/',
            {
                'source_account_id': source,
                'destination_account_id': destination,
                'amount_minor': 100,
                'currency': 'COP',
                'idempotency_key': f'funding-{uuid4()}',
            },
            format='json',
        )
        assert response.status_code == 400
    assert ledger_total() == 0


def test_funding_account_cannot_join_a_shared_expense():
    client = APIClient()
    payer = account(client, 'host', 1_000_000)
    response = client.post(
        '/api/shared-expenses/',
        {
            'title': 'Con la casa',
            'total_minor': 1000,
            'currency': 'COP',
            'payer_account_id': payer,
            'participant_account_ids': [payer, FUNDING],
            'split': 'equal',
        },
        format='json',
    )
    assert response.status_code == 400


def test_shared_expense_needs_at_least_two_participants():
    """An expense only the payer takes part in is not shared, and nobody owes
    anything on it. Rejecting it is clearer than storing a settled no-op."""
    client = APIClient()
    payer = account(client, 'solo', 1_000_000)
    response = client.post(
        '/api/shared-expenses/',
        {
            'title': 'Solo yo',
            'total_minor': 1000,
            'currency': 'COP',
            'payer_account_id': payer,
            'participant_account_ids': [payer],
            'split': 'equal',
        },
        format='json',
    )
    assert response.status_code == 400


def test_duplicate_participants_and_absent_payer_are_rejected():
    client = APIClient()
    payer = account(client, 'anfitrion', 1_000_000)
    guest = account(client, 'invitado')
    stranger = account(client, 'desconocido')
    base = {'title': 'x', 'total_minor': 900, 'currency': 'COP', 'split': 'equal'}

    duplicated = client.post(
        '/api/shared-expenses/',
        {**base, 'payer_account_id': payer, 'participant_account_ids': [payer, payer, guest]},
        format='json',
    )
    payer_outside = client.post(
        '/api/shared-expenses/',
        {**base, 'payer_account_id': stranger, 'participant_account_ids': [payer, guest]},
        format='json',
    )

    assert duplicated.status_code == 400
    assert payer_outside.status_code == 400


def test_overpayment_floors_outstanding_and_reports_the_excess():
    """The money already moved. The system describes that rather than denying it."""
    client = APIClient()
    payer = account(client, 'cobra', 1_000_000)
    debtor = account(client, 'paga', 5_000_000)
    third = account(client, 'tercero', 1_000_000)
    expense = client.post(
        '/api/shared-expenses/',
        {
            'title': 'Mercado',
            'total_minor': 900_000,
            'currency': 'COP',
            'payer_account_id': payer,
            'participant_account_ids': [payer, debtor, third],
            'split': 'equal',
        },
        format='json',
    ).json()

    client.post(
        '/api/transfers/',
        {
            'source_account_id': debtor,
            'destination_account_id': payer,
            'amount_minor': 500_000,
            'currency': 'COP',
            'idempotency_key': f'over-{uuid4()}',
            'shared_expense_id': expense['id'],
        },
        format='json',
    )

    detail = client.get(f'/api/shared-expenses/{expense["id"]}/').json()
    paid = {p['account_id']: p for p in detail['participants']}
    assert paid[debtor]['outstanding_minor'] == 0
    assert paid[debtor]['excess_minor'] == 200_000
    # Only the third participant still owes anything.
    assert detail['outstanding_total_minor'] == 300_000
    assert ledger_total() == 0


def test_expense_payment_must_flow_from_participant_to_payer():
    client = APIClient()
    payer = account(client, 'recibe', 1_000_000)
    debtor = account(client, 'debe', 1_000_000)
    expense = client.post(
        '/api/shared-expenses/',
        {
            'title': 'Taxi',
            'total_minor': 1000,
            'currency': 'COP',
            'payer_account_id': payer,
            'participant_account_ids': [payer, debtor],
            'split': 'equal',
        },
        format='json',
    ).json()

    reversed_direction = client.post(
        '/api/transfers/',
        {
            'source_account_id': payer,
            'destination_account_id': debtor,
            'amount_minor': 100,
            'currency': 'COP',
            'idempotency_key': f'rev-{uuid4()}',
            'shared_expense_id': expense['id'],
        },
        format='json',
    )
    assert reversed_direction.status_code == 400
    assert ledger_total() == 0


def test_transfer_referencing_an_unknown_expense_is_rejected():
    client = APIClient()
    source = account(client, 'origen', 1_000_000)
    destination = account(client, 'destino')
    response = client.post(
        '/api/transfers/',
        {
            'source_account_id': source,
            'destination_account_id': destination,
            'amount_minor': 100,
            'currency': 'COP',
            'idempotency_key': f'ghost-{uuid4()}',
            'shared_expense_id': str(uuid4()),
        },
        format='json',
    )
    assert response.status_code == 404
    assert ledger_total() == 0
