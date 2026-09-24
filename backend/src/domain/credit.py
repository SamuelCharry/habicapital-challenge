"""Del comportamiento en la billetera a una posición en el mapa de crédito.

Python puro. Sin Django, sin numpy, sin el modelo: aquí solo viven las reglas
que traducen conducta observable en las dos coordenadas que el modelo entiende.

El supuesto central, y hay que decirlo en voz alta: el dataset aporta la
*forma* de la población y dónde está la frontera. La correspondencia entre el
comportamiento de una persona en Colombia y esos ejes la definí yo, con los
rangos de referencia de abajo. No salió de los datos.
"""

from dataclasses import dataclass

from .errors import DomainError
from .money import Money

# Meses mínimos de actividad para situar a alguien. Por debajo de esto no hay
# constancia que medir, y una trayectoria inventada sería peor que no mostrar
# nada.
MINIMUM_MONTHS = 3

# Rangos de referencia para llevar conducta a las escalas del dataset, que
# están estandarizadas (media 0, desviación 1). Un ahorro mensual de
# 1.500.000 COP se considera el extremo alto de capacidad; 24 meses de
# constancia con cumplimiento perfecto, el extremo alto de estabilidad.
SAVINGS_CEILING_MINOR = 150_000_000
MONTHS_CEILING = 24

# Un millar de pesos, en unidades menores.
THOUSAND_PESOS = 100_000


class NotEnoughEvidence(DomainError):
    """No hay suficiente historial para situar a la persona."""


@dataclass(frozen=True)
class CreditProfile:
    """Lo que la billetera sabe de ti, en términos de crédito."""

    monthly_savings: Money
    months_consistent: int
    compliance_ratio: float | None
    down_payment: Money

    def __post_init__(self):
        if self.months_consistent < 0:
            raise DomainError('Los meses de constancia no pueden ser negativos.')
        if self.compliance_ratio is not None and not 0 <= self.compliance_ratio <= 1:
            raise DomainError('El cumplimiento debe estar entre 0 y 1.')

    @property
    def has_enough_evidence(self) -> bool:
        return self.months_consistent >= MINIMUM_MONTHS

    def coordinates(self) -> tuple[float, float]:
        """Las dos coordenadas del mapa: capacidad y estabilidad.

        Ambas se escalan aproximadamente al rango [-2, 2], que es donde vive la
        población del dataset una vez estandarizada.
        """
        if not self.has_enough_evidence:
            raise NotEnoughEvidence(
                f'Se necesitan al menos {MINIMUM_MONTHS} meses de actividad.'
            )

        capacity = _scaled(self.monthly_savings.amount_minor, SAVINGS_CEILING_MINOR)
        consistency = _scaled(self.months_consistent, MONTHS_CEILING)
        # El cumplimiento con gastos compartidos es historial de pago con
        # personas reales. Cuando no existe, no lo invento: pesa neutro.
        compliance = 0.0 if self.compliance_ratio is None else (self.compliance_ratio - 0.5) * 2
        stability = 0.65 * consistency + 0.35 * compliance * 2
        return round(capacity, 4), round(max(-2.5, min(2.5, stability)), 4)


def _scaled(value: float, ceiling: float) -> float:
    """Lleva [0, techo] a [-2, 2], recortando fuera de rango."""
    ratio = max(0.0, min(1.0, value / ceiling))
    return round(ratio * 4 - 2, 4)


def savings_advice(profile: CreditProfile, target_capacity: float) -> int:
    """El ahorro mensual, en unidades menores, que corresponde a una capacidad.

    Es la inversa de `_scaled`: sirve para traducir un punto de la trayectoria
    de vuelta a algo que una persona pueda hacer.
    """
    ratio = max(0.0, min(1.0, (target_capacity + 2) / 4))
    exact = ratio * SAVINGS_CEILING_MINOR
    # Se redondea al millar de pesos más cercano. La inversa de la escala
    # devuelve cifras como 829.875,76, y un consejo con centavos no es
    # accionable: nadie se propone ahorrar esa cantidad exacta.
    return int(round(exact / THOUSAND_PESOS) * THOUSAND_PESOS)


def months_advice(target_stability: float, compliance_ratio: float | None) -> int:
    """Los meses de constancia que corresponden a una estabilidad dada."""
    compliance = 0.0 if compliance_ratio is None else (compliance_ratio - 0.5) * 2
    consistency = (target_stability - 0.7 * compliance) / 0.65
    ratio = max(0.0, min(1.0, (consistency + 2) / 4))
    return int(round(ratio * MONTHS_CEILING))
