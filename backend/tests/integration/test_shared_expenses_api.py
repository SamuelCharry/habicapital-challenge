from uuid import uuid4

import pytest
from django.db import DatabaseError
from rest_framework.test import APIClient

from src.infrastructure.persistence.models import LedgerEntryModel, SharedExpenseModel, ParticipantModel
from src.domain.entities import EXTERNAL_FUNDING_ID
from tests.integration.test_transfers_api import account

pytestmark = pytest.mark.django_db


def create_expense(payer, participants, **changes):
    return APIClient().post('/api/shared-expenses/', dict(
        title='Dinner', total_minor=300, currency='COP', payer_account_id=payer,
        participant_account_ids=participants, split='equal',
    ) | changes, format='json')


def test_create_and_read_shared_expense():
    payer, bob, carol = [account(name) for name in ('payer', 'bobby', 'carol')]
    response = create_expense(payer, [carol, payer, bob], total_minor=301)
    assert response.status_code == 201
    detail = response.json()
    assert detail['title'] == 'Dinner' and detail['payer'] == payer
    assert sum(p['share_minor'] for p in detail['participants']) == 301
    assert [p['account_id'] for p in detail['participants']] == sorted([payer, bob, carol])
    payer_share = next(p for p in detail['participants'] if p['account_id'] == payer)
    assert payer_share['settled'] and payer_share['paid_minor'] == payer_share['share_minor']
    assert all(p['handle'] and p['display_name'] for p in detail['participants'])
    assert APIClient().get(f"/api/shared-expenses/{detail['id']}/").json() == detail
    assert APIClient().get('/api/shared-expenses/').json() == [detail]
    assert APIClient().get(f'/api/accounts/{bob}/shared-expenses/').json() == [detail]
    outsider = account('outsider')
    assert APIClient().get(f'/api/accounts/{outsider}/shared-expenses/').json() == []
    assert LedgerEntryModel.objects.count() == 0


@pytest.mark.parametrize('changes', [
    {'total_minor': 1}, {'total_minor': 0}, {'total_minor': -1},
    {'total_minor': True}, {'total_minor': 1.0}, {'total_minor': '100'},
    {'total_minor': 2**63}, {'currency': 'USD'}, {'split': 'percentage'},
    {'participant_account_ids': []}, {'title': ''},
])
def test_invalid_expense_rejected_without_writes(changes):
    payer, bob = account('payer'), account('bobby')
    assert create_expense(payer, [payer, bob], **changes).status_code == 400
    assert not SharedExpenseModel.objects.exists()
    assert not LedgerEntryModel.objects.exists()


def test_duplicate_participants_and_missing_payer_are_rejected():
    payer, bob = account('payer'), account('bobby')
    assert create_expense(payer, [payer, bob, bob]).status_code == 400
    assert create_expense(payer, [bob]).status_code == 400
    assert create_expense(payer, [payer, str(uuid4())]).status_code == 404
    assert APIClient().get(f'/api/shared-expenses/{uuid4()}/').status_code == 404
    assert APIClient().get(f'/api/accounts/{uuid4()}/shared-expenses/').status_code == 404
    assert not SharedExpenseModel.objects.exists()


def test_creation_rolls_back_agreement_if_participant_write_fails(monkeypatch):
    payer, bob = account('payer'), account('bobby')

    def fail(*args, **kwargs):
        raise DatabaseError('participant write failed')

    monkeypatch.setattr(ParticipantModel.objects, 'bulk_create', fail)
    with pytest.raises(DatabaseError, match='participant write failed'):
        create_expense(payer, [payer, bob])
    assert not SharedExpenseModel.objects.exists()
    assert not ParticipantModel.objects.exists()
    assert not LedgerEntryModel.objects.exists()


def test_funding_account_cannot_participate():
    payer = account('payer')
    assert create_expense(payer, [payer, str(EXTERNAL_FUNDING_ID)]).status_code == 400
    assert not SharedExpenseModel.objects.exists()


def test_total_equal_to_participant_count_assigns_one_unit_each():
    payer, bob = account('payer'), account('bobby')
    response = create_expense(payer, [payer, bob], total_minor=2)
    assert response.status_code == 201
    assert [p['share_minor'] for p in response.json()['participants']] == [1, 1]
