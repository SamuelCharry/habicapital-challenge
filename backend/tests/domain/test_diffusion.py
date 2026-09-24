"""El modelo de difusión escrito a mano, verificado contra algo conocido.

Un modelo generativo no se valida leyendo el código: se valida
entrenándolo sobre una distribución cuya forma conozco de antemano y
comprobando que la reproduce. Si la retropropagación manual tuviera un signo
cambiado, estas pruebas fallarían y ninguna revisión de código lo habría
notado.
"""

import sys
import pathlib

import numpy as np
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'scripts'))

from train_credit_model import (  # noqa: E402
    Denoiser, make_schedule, train_classifier, train_denoiser, qualify_probability,
)
from src.infrastructure.credit.diffusion import CreditModel, load_model  # noqa: E402


def two_moons(count=800, seed=3):
    """Dos medialunas entrelazadas: el ejemplo canónico de una distribución
    que ningún método lineal separa y que un modelo de difusión sí aprende."""
    rng = np.random.default_rng(seed)
    t = rng.uniform(0, np.pi, count)
    upper = np.stack([np.cos(t), np.sin(t)], axis=1)
    lower = np.stack([1 - np.cos(t), 0.5 - np.sin(t)], axis=1)
    points = np.concatenate([upper[: count // 2], lower[count // 2:]])
    return points + rng.normal(0, 0.08, points.shape)


def as_model(denoiser, points, total=200):
    """Envuelve un denoiser entrenado en la clase de inferencia real."""
    return CreditModel({
        'w1': denoiser.w1, 'b1': denoiser.b1,
        'w2': denoiser.w2, 'b2': denoiser.b2,
        'w3': denoiser.w3, 'b3': denoiser.b3,
        'classifier': np.zeros(6),
        'population': points,
        'population_good': np.ones(len(points)),
        'total_steps': total,
    })


@pytest.fixture(scope='module')
def moons_model():
    points = two_moons()
    denoiser, _ = train_denoiser(points, steps=4000)
    return as_model(denoiser, points), points


def test_training_reduces_the_loss():
    """Lo mínimo: que el gradiente vaya en la dirección correcta."""
    _, losses = train_denoiser(two_moons(count=400), steps=2000)
    first, last = losses[0][1], losses[-1][1]
    assert last < first / 2, f'la pérdida pasó de {first:.3f} a {last:.3f}'


def test_samples_land_on_the_learned_distribution(moons_model):
    """Cada muestra generada cae cerca de algún punto real.

    Es la prueba de que el modelo aprendió la variedad y no una nube difusa
    alrededor del promedio.
    """
    model, points = moons_model
    generated = model.sample(300, seed=1)
    distances = np.linalg.norm(generated[:, None, :] - points[None, :, :], axis=2).min(axis=1)
    assert np.median(distances) < 0.2, f'mediana de distancia {np.median(distances):.3f}'
    assert (distances < 0.35).mean() > 0.85


def test_samples_reproduce_both_modes(moons_model):
    """Las dos medialunas aparecen, no solo una.

    El colapso de modos es la forma típica en que un modelo generativo falla
    pareciendo que funciona: aprende una parte de la distribución y la
    repite.
    """
    model, _ = moons_model
    generated = model.sample(400, seed=2)
    upper = ((generated[:, 1] > 0.25) & (generated[:, 0] < 0.5)).sum()
    lower = ((generated[:, 1] < 0.25) & (generated[:, 0] > 0.5)).sum()
    assert upper > 60 and lower > 60, f'arriba={upper} abajo={lower}'


def test_projection_pulls_an_invented_point_onto_the_manifold(moons_model):
    """Un punto inventado, en una zona vacía, se corrige hacia donde hay datos.

    Esto es exactamente lo que impide que la recomendación sea un consejo
    imposible: el contrafactual ingenuo se queda en el vacío, este vuelve.
    """
    model, points = moons_model
    invented = np.array([[0.5, 1.6]])
    distance_before = np.linalg.norm(points - invented, axis=1).min()

    # Reproyectar es muestrear, o sea que es estocastico. Afirmar sobre una
    # sola semilla seria un test inestable: mido la mediana de varias.
    distances = [
        np.linalg.norm(
            points - model.project_to_manifold(invented, strength=60, seed=seed)[0],
            axis=1,
        ).min()
        for seed in range(8)
    ]
    assert np.median(distances) < distance_before * 0.25, (
        f'de {distance_before:.3f} a {np.median(distances):.3f}'
    )


def test_classifier_beats_the_majority_class():
    """Un clasificador que no supera 'predecí siempre la clase mayoritaria'
    no aporta nada, y sobre él no se puede construir una recomendación."""
    points = two_moons(count=600)
    labels = (points[:, 1] > 0.25).astype(float)
    weights = train_classifier(points, labels)
    accuracy = ((qualify_probability(points, weights) > 0.5) == labels).mean()
    assert accuracy > max(labels.mean(), 1 - labels.mean()) + 0.15


def test_noise_schedule_destroys_the_signal():
    """Si al final de la cadena queda senal, muestrear desde ruido puro no es
    valido: el modelo nunca vio algo tan ruidoso durante el entrenamiento."""
    _, _, alpha_bar = make_schedule(200)
    assert alpha_bar[0] > 0.99
    assert alpha_bar[-1] < 0.02, f'queda {np.sqrt(alpha_bar[-1]):.2f} de senal'
    assert np.all(np.diff(alpha_bar) < 0)


def test_training_and_inference_share_the_same_schedule():
    """El planificador esta escrito dos veces: en el entrenamiento y en la
    inferencia. Si se separan, el artefacto se denoisa con una cadena que no
    es la que aprendio, y falla en silencio."""
    _, _, trained = make_schedule(200)
    served = load_model().alpha_bar
    assert np.allclose(trained, served)


def test_time_encoding_separates_steps():
    """Si el denoiser no distingue en qué paso está, no puede quitar la
    cantidad correcta de ruido."""
    denoiser = Denoiser()
    x = np.zeros((1, 2))
    early = denoiser.forward(x, np.array([5]), 200)[0]
    late = denoiser.forward(x, np.array([190]), 200)[0]
    assert np.linalg.norm(early - late) > 1e-3


# --- el artefacto que se sirve de verdad ---------------------------------

def test_shipped_model_loads_and_is_shaped_right():
    model = load_model()
    assert model.population.shape == (1000, 2)
    assert model.total_steps == 200
    assert model.w1.shape == (10, 128)


def test_shipped_model_trajectory_moves_toward_qualifying():
    """La trayectoria tiene que mejorar la probabilidad, o no es una ruta."""
    model = load_model()
    start = (-1.2, -1.0)
    path, probabilities = model.guided_path(start, seed=1)
    assert len(path) == 25
    assert probabilities[-1] > probabilities[0]
    assert probabilities[-1] > 0.6


def test_shipped_trajectory_stays_near_real_people():
    """Cada punto del camino corresponde a alguien que podría existir.

    Sin esto la recomendación sería un ejemplo adversarial: un punto que
    voltea el clasificador pero que no describe a ninguna persona real.
    """
    model = load_model()
    path, _ = model.guided_path((-1.2, -1.0), seed=1)
    distances = np.linalg.norm(
        path[:, None, :] - model.population[None, :, :], axis=2
    ).min(axis=1)
    assert distances.max() < 0.6, f'el punto más alejado queda a {distances.max():.3f}'
