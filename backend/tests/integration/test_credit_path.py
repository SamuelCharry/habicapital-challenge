"""La ruta al crédito, de punta a punta.

Lo que se prueba aquí no es el modelo —eso está en tests/domain/test_diffusion.py—
sino la traducción: que el comportamiento guardado en el ledger se convierta en
un perfil correcto, y que los tres estados del producto se comporten.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from rest_framework.test import APIClient

from src.application.credit_service import CreditPathService, QUALIFIES_AT
from src.domain.credit import MINIMUM_MONTHS, CreditProfile, NotEnoughEvidence
from src.domain.money import Money
from src.infrastructure.container import build_wallet
from src.infrastructure.credit.diffusion import load_model
from src.infrastructure.persistence.repositories import (
    DjangoAccountRepository,
    DjangoLedgerRepository,
    DjangoSharedExpenseRepository,
)

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


def account(client, handle):
    created = client.post(
        '/api/accounts/', {'handle': handle, 'display_name': handle.title()}, format='json'
    )
    assert created.status_code == 201, created.json()
    return UUID(created.json()['id'])


def deposit_history(account_id, months, monthly_pesos):
    """Deposita una vez por mes hacia atrás, usando el reloj inyectable."""
    from src.application.commands import DepositCommand
    from src.application.services import DepositService

    for index in range(months):
        moment = NOW - timedelta(days=30 * (months - 1 - index))
        DepositService(
            DjangoAccountRepository(), DjangoLedgerRepository(), clock=lambda m=moment: m
        ).deposit(DepositCommand(account_id, Money(monthly_pesos * 100)))


def path(account_id):
    return CreditPathService(
        DjangoAccountRepository(), DjangoLedgerRepository(),
        DjangoSharedExpenseRepository(), load_model,
    ).path_for(account_id)


# --- derivación del perfil ------------------------------------------------

def test_profile_counts_distinct_months_not_deposits():
    """Diez depósitos en un mismo mes no son diez meses de constancia."""
    client = APIClient()
    account_id = account(client, 'apurado')
    for _ in range(10):
        client.post(
            f'/api/accounts/{account_id}/deposits/',
            {'amount_minor': 10_000_00, 'currency': 'COP'}, format='json',
        )
    profile = path(account_id).profile
    assert profile.months_consistent == 1


def test_profile_averages_savings_over_months():
    client = APIClient()
    account_id = account(client, 'constante')
    deposit_history(account_id, months=6, monthly_pesos=500_000)
    profile = path(account_id).profile
    assert profile.months_consistent == 6
    assert profile.monthly_savings.amount_minor == 500_000_00


def test_compliance_is_none_without_shared_expenses():
    """No haber tenido la oportunidad de incumplir no es haber incumplido."""
    client = APIClient()
    account_id = account(client, 'solitario')
    deposit_history(account_id, months=5, monthly_pesos=400_000)
    assert path(account_id).profile.compliance_ratio is None


def test_compliance_reflects_what_was_actually_paid():
    client = APIClient()
    payer = account(client, 'anfitriona')
    debtor = account(client, 'deudor')
    deposit_history(payer, months=5, monthly_pesos=900_000)
    deposit_history(debtor, months=5, monthly_pesos=900_000)
    expense = client.post(
        '/api/shared-expenses/',
        {
            'title': 'Mercado', 'total_minor': 400_000_00, 'currency': 'COP',
            'payer_account_id': str(payer), 'participant_account_ids': [str(payer), str(debtor)],
            'split': 'equal',
        }, format='json',
    ).json()

    assert path(debtor).profile.compliance_ratio == 0.0

    client.post('/api/transfers/', {
        'source_account_id': str(debtor), 'destination_account_id': str(payer),
        'amount_minor': 200_000_00, 'currency': 'COP',
        'idempotency_key': f'pago-{uuid4()}', 'shared_expense_id': expense['id'],
    }, format='json')

    assert path(debtor).profile.compliance_ratio == 1.0


# --- los tres estados del producto ---------------------------------------

def test_without_enough_history_there_is_no_trajectory():
    """Inventarle una ruta a quien no tiene historial sería peor que no
    mostrar nada: la recomendación no estaría respaldada por evidencia."""
    client = APIClient()
    account_id = account(client, 'nuevo')
    deposit_history(account_id, months=MINIMUM_MONTHS - 1, monthly_pesos=300_000)
    result = path(account_id)
    assert result.has_enough_evidence is False
    assert result.trajectory == [] and result.steps == []
    assert result.population, 'el mapa se muestra aunque no haya punto propio'


def test_someone_who_already_qualifies_gets_no_route():
    """Trazarle una ruta a quien ya califica lo movería hacia el centro del
    grupo, que puede ser una posición peor. Eso sería mentir."""
    client = APIClient()
    account_id = account(client, 'solvente')
    deposit_history(account_id, months=18, monthly_pesos=1_400_000)
    result = path(account_id)
    assert result.has_enough_evidence is True
    assert result.trajectory == []
    assert len(result.steps) == 1


def test_someone_close_gets_a_route_that_improves_the_odds():
    client = APIClient()
    account_id = account(client, 'encamino')
    deposit_history(account_id, months=7, monthly_pesos=420_000)
    result = path(account_id)
    assert result.has_enough_evidence is True
    assert len(result.trajectory) == 25
    assert result.trajectory[-1].qualify_probability > result.trajectory[0].qualify_probability
    assert 1 <= len(result.steps) <= 3


def test_trajectory_never_recommends_going_backwards():
    """Cada paso sugerido tiene que pedir más ahorro o más tiempo, nunca
    menos: una ruta que recomiende ahorrar menos es un error de signo."""
    client = APIClient()
    account_id = account(client, 'progresiva')
    deposit_history(account_id, months=7, monthly_pesos=420_000)
    result = path(account_id)
    destination = result.trajectory[-1]
    assert destination.monthly_savings.amount_minor >= result.profile.monthly_savings.amount_minor
    assert destination.months_consistent >= result.profile.months_consistent


# --- dominio puro ---------------------------------------------------------

def test_coordinates_require_evidence():
    profile = CreditProfile(Money(100_000_00), 1, None, Money(100_000_00))
    with pytest.raises(NotEnoughEvidence):
        profile.coordinates()


def test_coordinates_are_bounded():
    """Un ahorro absurdo no debe sacar el punto fuera del mapa."""
    profile = CreditProfile(Money(999_999_999_00), 240, 1.0, Money(0))
    capacity, stability = profile.coordinates()
    assert -2.5 <= capacity <= 2.5 and -2.5 <= stability <= 2.5


# --- el endpoint ----------------------------------------------------------

def test_endpoint_returns_the_map_and_the_disclaimer_shape():
    client = APIClient()
    account_id = account(client, 'porhttp')
    deposit_history(account_id, months=7, monthly_pesos=420_000)
    response = client.get(f'/api/accounts/{account_id}/credit-path/')

    assert response.status_code == 200
    body = response.json()
    assert len(body['population']) == 1000
    assert all(len(point) == 3 for point in body['population'])
    assert body['profile']['months_consistent'] == 7
    assert body['trajectory'][0]['qualify_probability'] <= 1.0


def test_endpoint_404s_for_an_unknown_account():
    assert APIClient().get(f'/api/accounts/{uuid4()}/credit-path/').status_code == 404


def test_credit_path_writes_nothing_to_the_ledger():
    """Consultar la ruta es una lectura. Si escribiera algo sería un defecto
    grave: una consulta no puede mover plata."""
    client = APIClient()
    account_id = account(client, 'lectura')
    deposit_history(account_id, months=7, monthly_pesos=420_000)
    from src.infrastructure.persistence.models import LedgerEntryModel

    before = LedgerEntryModel.objects.count()
    client.get(f'/api/accounts/{account_id}/credit-path/')
    assert LedgerEntryModel.objects.count() == before
    assert DjangoLedgerRepository().total_balance().amount_minor == 0


def test_facade_exposes_the_path():
    client = APIClient()
    account_id = account(client, 'fachada')
    deposit_history(account_id, months=7, monthly_pesos=420_000)
    assert build_wallet().credit_path(account_id).has_enough_evidence is True


def test_qualifying_threshold_is_shared_with_the_model():
    """El umbral de producto y el que usa el modelo para elegir destino tienen
    que ser el mismo, o el destino no calificaría según la propia app."""
    model = load_model()
    target = model.target_point((-1.0, -1.0))
    assert float(model.qualify_probability(target)[0]) >= QUALIFIES_AT - 0.05
