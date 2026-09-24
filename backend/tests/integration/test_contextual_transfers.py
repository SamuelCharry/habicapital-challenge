from uuid import UUID, uuid4

import pytest
from django.db import connection, transaction, DatabaseError
from rest_framework.test import APIClient

from src.application.event_handlers import SharedExpenseUpdater
from src.domain.events import TransferCompleted
from src.domain.entities import EXTERNAL_FUNDING_ID
from src.infrastructure.container import build_wallet
from src.infrastructure.persistence.models import AccountModel, LedgerEntryModel, TransferOperationModel
from src.infrastructure.persistence.repositories import DjangoAccountRepository, DjangoLedgerRepository, DjangoTransferOperationRepository
from tests.integration.test_transfer_concurrency import concurrently
from tests.integration.test_shared_expenses_api import create_expense
from tests.integration.test_transfers_api import account, deposit, payload, post

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def funding_account():
    # Transactional tests flush the migration's seed data between tests.
    AccountModel.objects.get_or_create(
        pk=EXTERNAL_FUNDING_ID,
        defaults=dict(handle='EXTERNAL_FUNDING', display_name='Funding', allows_negative_balance=True),
    )


def setup_expense():
    payer, bob, carol = [account(name) for name in ('payer', 'bobby', 'carol')]
    deposit(bob, 1000)
    deposit(carol, 1000)
    expense = create_expense(payer, [payer, bob, carol]).json()
    return payer, bob, carol, expense['id']


def detail(expense):
    return APIClient().get(f'/api/shared-expenses/{expense}/').json()


def pay(source, payer, expense, **changes):
    return post(payload(source, payer, shared_expense_id=expense, **changes))


def test_transfer_linked_to_expense_reduces_outstanding():
    payer, bob, _, expense = setup_expense()
    response = pay(bob, payer, expense, amount_minor=40)
    assert response.status_code == 201 and response.json()['shared_expense_id'] == expense
    participant = next(p for p in detail(expense)['participants'] if p['account_id'] == bob)
    assert participant['paid_minor'] == 40 and participant['outstanding_minor'] == 60
    assert detail(expense)['outstanding_total_minor'] == 160


def test_expense_settles_when_all_participants_have_paid():
    payer, bob, carol, expense = setup_expense()
    assert pay(bob, payer, expense).status_code == 201
    assert pay(carol, payer, expense, idempotency_key='carol-key').status_code == 201
    assert detail(expense)['settled'] and detail(expense)['outstanding_total_minor'] == 0


def test_expense_update_failure_does_not_roll_back_the_transfer(monkeypatch, caplog):
    payer, bob, _, expense = setup_expense()
    calls = []

    def fail(self, event):
        assert not connection.in_atomic_block
        assert isinstance(event, TransferCompleted)
        assert LedgerEntryModel.objects.filter(operation_id=event.operation_id).count() == 2
        calls.append(event)
        raise RuntimeError('expense update failed')

    monkeypatch.setattr(SharedExpenseUpdater, '__call__', fail)
    assert pay(bob, payer, expense).status_code == 201
    assert len(calls) == 1 and 'expense update failed' in caplog.text
    repo = DjangoAccountRepository()
    assert repo.balance_of(UUID(bob)).amount_minor == 900
    assert repo.balance_of(UUID(payer)).amount_minor == 100
    assert DjangoLedgerRepository().total_balance().amount_minor == 0
    assert detail(expense)['outstanding_total_minor'] == 100


def test_transfer_from_non_participant_to_payer_is_rejected():
    payer, _, _, expense = setup_expense()
    outsider = account('outsider')
    deposit(outsider, 100)
    assert pay(outsider, payer, expense).status_code == 400
    assert not TransferOperationModel.objects.exists()


def test_transfer_to_non_payer_is_rejected():
    _, bob, carol, expense = setup_expense()
    assert pay(bob, carol, expense).status_code == 400
    assert not TransferOperationModel.objects.exists()


def test_overpayment_floors_outstanding_at_zero_and_reports_excess():
    payer, bob, _, expense = setup_expense()
    assert pay(bob, payer, expense, amount_minor=140).status_code == 201
    participant = next(p for p in detail(expense)['participants'] if p['account_id'] == bob)
    assert participant['paid_minor'] == 140
    assert participant['outstanding_minor'] == 0 and participant['settled']
    assert participant['excess_minor'] == 40


def test_history_includes_expense_context():
    payer, bob, _, expense = setup_expense()
    assert pay(bob, payer, expense).status_code == 201
    assert post(payload(bob, payer, idempotency_key='unlinked-key')).status_code == 201
    for account_id in (payer, bob):
        history = APIClient().get(f'/api/accounts/{account_id}/history/').json()
        linked = [e for e in history if e['shared_expense_id'] == expense]
        assert len(linked) == 1 and linked[0]['shared_expense_title'] == 'Dinner'
        assert all(e['shared_expense_title'] is None for e in history if e['shared_expense_id'] is None)


def test_conservation_holds_after_expense_workflow():
    payer, bob, carol, expense = setup_expense()
    for i, (sender, amount) in enumerate([(bob, 30), (bob, 70), (carol, 130)]):
        assert pay(sender, payer, expense, amount_minor=amount, idempotency_key=f'workflow-{i}').status_code == 201
    assert DjangoLedgerRepository().total_balance().amount_minor == 0
    for operation in TransferOperationModel.objects.all():
        assert sum(LedgerEntryModel.objects.filter(operation_id=operation.operation_id).values_list('amount_minor', flat=True)) == 0
    assert detail(expense)['settled']


def test_linked_retry_does_not_double_count_or_republish(monkeypatch):
    payer, bob, _, expense = setup_expense()
    calls = []
    monkeypatch.setattr(SharedExpenseUpdater, '__call__', lambda self, event: calls.append(event))
    first = pay(bob, payer, expense)
    replay = pay(bob, payer, expense)
    assert replay.status_code == 200 and replay.json() == first.json() | {'replayed': True}
    assert len(calls) == 1 and detail(expense)['outstanding_total_minor'] == 100
    assert pay(bob, payer, None).status_code == 409
    assert pay(bob, payer, str(uuid4())).status_code == 409


def test_event_waits_for_outer_commit_and_is_discarded_on_rollback(monkeypatch):
    payer, bob, _, expense = setup_expense()
    calls = []
    monkeypatch.setattr(SharedExpenseUpdater, '__call__', lambda self, event: calls.append(event))
    wallet = build_wallet()
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            wallet.transfer(UUID(bob), UUID(payer), 100, 'COP', 'rollback-key', UUID(expense))
            assert calls == []
            raise RuntimeError('rollback')
    assert calls == [] and not TransferOperationModel.objects.exists()
    with transaction.atomic():
        wallet.transfer(UUID(bob), UUID(payer), 100, 'COP', 'commit-key', UUID(expense))
        assert calls == []
    assert len(calls) == 1


def test_concurrent_linked_retries_count_payment_once():
    payer, bob, _, expense = setup_expense()
    responses = concurrently([lambda: pay(bob, payer, expense) for _ in range(4)])
    assert sorted(r.status_code for r in responses) == [200, 200, 200, 201]
    assert len({r.json()['operation_id'] for r in responses}) == 1
    assert TransferOperationModel.objects.count() == 1
    assert detail(expense)['outstanding_total_minor'] == 100
    assert DjangoLedgerRepository().total_balance().amount_minor == 0


def test_link_failure_rolls_back_claim_and_dispatches_nothing(monkeypatch):
    payer, bob, _, expense = setup_expense()
    calls = []
    original = DjangoTransferOperationRepository.link_expense

    def fail(self, *args):
        original(self, *args)
        raise DatabaseError('link failed')

    monkeypatch.setattr(DjangoTransferOperationRepository, 'link_expense', fail)
    monkeypatch.setattr(SharedExpenseUpdater, '__call__', lambda self, event: calls.append(event))
    with pytest.raises(DatabaseError, match='link failed'):
        pay(bob, payer, expense)
    assert calls == [] and not TransferOperationModel.objects.exists()
    assert not LedgerEntryModel.objects.filter(operation_type='transfer').exists()
    assert detail(expense)['outstanding_total_minor'] == 200


def test_failed_linked_transfer_cannot_change_payment_state_or_publish(monkeypatch):
    payer, bob, _, expense = setup_expense()
    calls = []
    monkeypatch.setattr(SharedExpenseUpdater, '__call__', lambda self, event: calls.append(event))
    assert pay(bob, payer, expense, amount_minor=1001).status_code == 422
    assert pay(payer, payer, expense).status_code == 400
    assert pay(bob, payer, str(uuid4())).status_code == 404
    assert pay(bob, payer, 'invalid-id').status_code == 400
    assert calls == [] and not TransferOperationModel.objects.exists()
    assert not LedgerEntryModel.objects.filter(operation_type='transfer').exists()
    assert detail(expense)['outstanding_total_minor'] == 200
