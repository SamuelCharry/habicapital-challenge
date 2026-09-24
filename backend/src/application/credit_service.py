"""Deriva el perfil crediticio del historial y calcula la ruta.

Vive en la capa de aplicación porque orquesta: lee del ledger y de los gastos
compartidos, arma el objeto de dominio, y le pide al modelo la trayectoria.
Ninguna regla de traducción vive aquí — esas están en `domain/credit.py`.

No abre transacción: solo lee.
"""

from dataclasses import dataclass
from datetime import timezone
from uuid import UUID

from src.domain.credit import (
    CreditProfile,
    months_advice,
    savings_advice,
)
from src.domain.money import Money
from src.domain.repositories import (
    AccountRepository,
    LedgerRepository,
    SharedExpenseRepository,
)


# Umbral de "califica". Es el mismo que usa el modelo para elegir el destino;
# vive aquí porque es una decisión de producto, no del clasificador.
QUALIFIES_AT = 0.72


@dataclass(frozen=True)
class Waypoint:
    capacity: float
    stability: float
    qualify_probability: float
    monthly_savings: Money
    months_consistent: int


@dataclass(frozen=True)
class Step:
    order: int
    action: str
    magnitude: str


@dataclass(frozen=True)
class CreditPath:
    profile: CreditProfile
    has_enough_evidence: bool
    headline: str
    # Perfiles reales del dataset: [capacidad, estabilidad, P(califica)].
    population: list[tuple[float, float, float]]
    # Perfiles que el modelo generó. Densifican el mapa y son la prueba
    # visual de que aprendió la distribución: se superponen a los reales.
    generated: list[tuple[float, float, float]]
    trajectory: list[Waypoint]
    steps: list[Step]


class CreditPathService:
    def __init__(
        self,
        accounts: AccountRepository,
        ledger: LedgerRepository,
        expenses: SharedExpenseRepository,
        model_loader,
    ):
        self.accounts = accounts
        self.ledger = ledger
        self.expenses = expenses
        self.model_loader = model_loader

    # --- derivación del perfil -------------------------------------------

    def profile_for(self, account_id: UUID) -> CreditProfile:
        self.accounts.get(account_id)
        entries = self.ledger.entries_for(account_id)
        deposits = [e for e in entries if e.operation_type == 'deposit' and e.money.is_positive]

        months = sorted({(e.created_at.astimezone(timezone.utc).year,
                          e.created_at.astimezone(timezone.utc).month) for e in deposits})
        total_deposited = sum(e.money.amount_minor for e in deposits)
        monthly = total_deposited // len(months) if months else 0

        return CreditProfile(
            monthly_savings=Money(int(monthly)),
            months_consistent=len(months),
            compliance_ratio=self._compliance(account_id),
            down_payment=self.accounts.balance_of(account_id),
        )

    def _compliance(self, account_id: UUID) -> float | None:
        """Qué proporción de lo que debías en gastos compartidos ya cubriste.

        Es historial de pago con personas reales, que es exactamente lo que un
        originador quiere ver. Si no participas en ningún gasto, devuelve None
        en vez de 0: no haber tenido la oportunidad de incumplir no es lo
        mismo que haber incumplido.
        """
        owed = paid = 0
        for expense in self.expenses.list_expenses(account_id):
            for participant in expense.participants:
                if participant.account.id != account_id or account_id == expense.payer:
                    continue
                owed += participant.share.amount_minor
                paid += min(participant.paid_minor, participant.share.amount_minor)
        if owed == 0:
            return None
        return round(paid / owed, 4)

    # --- la ruta ----------------------------------------------------------

    def path_for(self, account_id: UUID) -> CreditPath:
        profile = self.profile_for(account_id)
        model = self.model_loader()
        def as_points(coordinates):
            if not len(coordinates):
                return []
            probabilities = model.qualify_probability(coordinates)
            return [
                (round(float(x), 3), round(float(y), 3), round(float(p), 3))
                for (x, y), p in zip(coordinates, probabilities)
            ]

        population = as_points(model.population)
        generated = as_points(model.generated)

        if not profile.has_enough_evidence:
            return CreditPath(
                profile=profile,
                has_enough_evidence=False,
                headline='Todavía no podemos situarte en el mapa.',
                population=population,
                generated=generated,
                trajectory=[],
                steps=[],
            )

        start = profile.coordinates()
        if float(model.qualify_probability(start)[0]) >= QUALIFIES_AT:
            # Ya está dentro. Trazarle una ruta lo movería hacia el centro del
            # grupo que califica, que puede estar en una posición algo peor que
            # la suya: mostrar eso como "mejora" sería falso.
            return CreditPath(
                profile=profile,
                has_enough_evidence=True,
                headline='Hoy ya estás dentro del grupo que califica.',
                population=population,
                generated=generated,
                trajectory=[],
                steps=[Step(
                    order=1,
                    action='Mantén tu ahorro y tu cumplimiento como van',
                    magnitude='continuo',
                )],
            )

        path, probabilities = model.guided_path(start)
        trajectory = [
            Waypoint(
                capacity=round(float(x), 4),
                stability=round(float(y), 4),
                qualify_probability=round(float(p), 4),
                monthly_savings=Money(savings_advice(profile, float(x))),
                months_consistent=months_advice(float(y), profile.compliance_ratio),
            )
            for (x, y), p in zip(path, probabilities)
        ]
        return CreditPath(
            profile=profile,
            has_enough_evidence=True,
            headline=self._headline(trajectory),
            population=population,
            generated=generated,
            trajectory=trajectory,
            steps=self._steps(profile, trajectory),
        )

    @staticmethod
    def _headline(trajectory: list[Waypoint]) -> str:
        return 'Estás cerca del grupo que califica.'

    @staticmethod
    def _steps(profile: CreditProfile, trajectory: list[Waypoint]) -> list[Step]:
        """La trayectoria traducida a tres acciones. Tres, no siete.

        Más de tres deja de ser accionable, y cada paso extra es una cifra que
        el usuario no va a retener.
        """
        destination = trajectory[-1]
        extra_savings = destination.monthly_savings.amount_minor - profile.monthly_savings.amount_minor
        extra_months = destination.months_consistent - profile.months_consistent

        steps = []
        if extra_months > 0:
            steps.append(Step(
                order=len(steps) + 1,
                action=f'Sostén tu ahorro {extra_months} meses más',
                magnitude=f'~{extra_months} meses',
            ))
        if extra_savings > 0:
            steps.append(Step(
                order=len(steps) + 1,
                action=f'Sube el ahorro mensual a {_pesos(destination.monthly_savings)}',
                magnitude=f'+{_pesos(Money(extra_savings))}',
            ))
        if profile.compliance_ratio is None:
            steps.append(Step(
                order=len(steps) + 1,
                action='Registra un gasto compartido para construir historial de pago',
                magnitude='sin historial aún',
            ))
        else:
            steps.append(Step(
                order=len(steps) + 1,
                action='Mantén tu cumplimiento en gastos compartidos',
                magnitude='continuo',
            ))
        return steps[:3]


def _pesos(money: Money) -> str:
    return f'${money.amount_minor // 100:,.0f}'.replace(',', '.')
