"""Siembra datos de demostración con historial de varios meses.

    python scripts/seed_demo.py

Borra todo y vuelve a crear. Usa los servicios reales con un reloj inyectado
en vez de escribir SQL: así los depósitos quedan fechados hacia atrás pero
pasan por el mismo camino que los de producción, y el ledger sigue cuadrando.

El reloj es inyectable porque los servicios reciben sus dependencias. Ese
detalle, que parecía sobra al diseñarlos, es lo que hace posible este script.
"""

import os
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import django

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection, transaction  # noqa: E402

from src.application.commands import (  # noqa: E402
    CreateAccountCommand,
    CreateSharedExpenseCommand,
    DepositCommand,
    TransferCommand,
)
from src.application.services import (  # noqa: E402
    AccountService,
    DepositService,
    SharedExpenseService,
    TransferService,
)
from src.domain.entities import EXTERNAL_FUNDING_ID  # noqa: E402
from src.domain.money import Money  # noqa: E402
from src.infrastructure.persistence.repositories import (  # noqa: E402
    DjangoAccountRepository,
    DjangoLedgerRepository,
    DjangoSharedExpenseRepository,
    DjangoTransferOperationRepository,
)

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

NOW = datetime.now(timezone.utc)

PEOPLE = [
    # handle, nombre, meses de historial, ahorro mensual en pesos
    ('samuel', 'Samuel Charry', 14, 800_000),
    ('juan', 'Juan Pérez', 9, 450_000),
    ('laura', 'Laura Gómez', 6, 1_200_000),
    # Mariana existe para poder mostrar el estado "sin evidencia suficiente".
    ('mariana', 'Mariana Ríos', 1, 300_000),
]


def wipe():
    """Vacía las tablas. El trigger de append-only impide borrar asientos, así
    que se retira y se vuelve a poner — es la única operación del proyecto que
    tiene permitido tocarlo, y solo porque esto no es producción."""
    with connection.cursor() as cursor:
        cursor.execute('DROP TRIGGER IF EXISTS ledger_append_only ON persistence_ledgerentrymodel')
        cursor.execute(
            'TRUNCATE persistence_ledgerentrymodel, persistence_transferoperationmodel, '
            'persistence_participantmodel, persistence_sharedexpensemodel CASCADE'
        )
        cursor.execute(
            'DELETE FROM persistence_accountmodel WHERE id <> %s', [str(EXTERNAL_FUNDING_ID)]
        )
        cursor.execute(
            'CREATE TRIGGER ledger_append_only BEFORE UPDATE OR DELETE '
            'ON persistence_ledgerentrymodel FOR EACH ROW '
            'EXECUTE FUNCTION reject_ledger_mutation()'
        )


def services(moment):
    """Construye los servicios con el reloj fijado en `moment`."""
    accounts = DjangoAccountRepository()
    ledger = DjangoLedgerRepository()
    expenses = DjangoSharedExpenseRepository()
    clock = lambda: moment
    return (
        AccountService(accounts, ledger, expenses=expenses),
        DepositService(accounts, ledger, clock=clock),
        TransferService(
            accounts, ledger, DjangoTransferOperationRepository(),
            expenses=expenses, clock=clock,
        ),
        SharedExpenseService(accounts, expenses),
    )


def main():
    wipe()
    account_service, _, _, _ = services(NOW)
    ids = {}
    for handle, name, _, _ in PEOPLE:
        ids[handle] = account_service.create(CreateAccountCommand(handle, name)).account.id
        print(f'cuenta @{handle}')

    for handle, _, months, monthly in PEOPLE:
        for index in range(months):
            moment = NOW - timedelta(days=30 * (months - 1 - index))
            _, deposits, _, _ = services(moment)
            deposits.deposit(DepositCommand(ids[handle], Money(monthly * 100)))
        print(f'@{handle}: {months} depósitos de ${monthly:,}'.replace(',', '.'))

    _, _, transfers, expense_service = services(NOW)
    plans = [
        ('Cena del viernes', 180_000, 'samuel', ['samuel', 'juan', 'laura']),
        ('Arriendo noviembre', 2_400_000, 'laura', ['laura', 'samuel', 'mariana']),
        ('Mercado del mes', 480_000, 'juan', ['juan', 'samuel', 'laura']),
    ]
    expenses = {}
    for title, total, payer, members in plans:
        expenses[title] = expense_service.create(CreateSharedExpenseCommand(
            title, Money(total * 100), ids[payer],
            tuple(ids[m] for m in members), 'equal',
        ))
        print(f'gasto "{title}" ${total:,}'.replace(',', '.'))

    # Pagos: algunos cubiertos, otros no, para que la demo tenga ambos estados.
    payments = [
        ('juan', 'samuel', 60_000, 'Cena del viernes'),
        ('samuel', 'laura', 800_000, 'Arriendo noviembre'),
        ('laura', 'juan', 160_000, 'Mercado del mes'),
        ('samuel', 'juan', 160_000, 'Mercado del mes'),
    ]
    for source, destination, amount, title in payments:
        transfers.transfer(TransferCommand(
            ids[source], ids[destination], Money(amount * 100),
            f'seed-{source}-{title[:12]}'.replace(' ', '-').lower(),
            expenses[title].id,
        ))
        print(f'@{source} -> @{destination} ${amount:,} · {title}'.replace(',', '.'))

    # Una transferencia sin contexto, para que el historial muestre la
    # diferencia entre un pago con gasto asociado y uno suelto.
    transfers.transfer(TransferCommand(
        ids['samuel'], ids['mariana'], Money(35_000 * 100), 'seed-suelta-sin-contexto', None,
    ))
    print('@samuel -> @mariana $35.000 · sin gasto asociado')

    total = DjangoLedgerRepository().total_balance()
    print(f'\nconservación: suma del ledger = {total.amount_minor}')
    if total.amount_minor != 0:
        raise SystemExit('el ledger no cuadra')


if __name__ == '__main__':
    with transaction.atomic():
        pass
    main()
