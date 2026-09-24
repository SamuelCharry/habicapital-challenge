"""Entrena el modelo de difusión sobre el dataset UCI German Credit.

Se corre a mano, no en el camino de un request. Produce un único artefacto
(`model.npz`) que el backend carga y ejecuta con numpy puro.

    python scripts/train_credit_model.py

Por qué a mano y no con PyTorch: el denoiser son ~18.000 parámetros. Una
dependencia de 200 MB para eso cuesta más de lo que da, y escribirlo a mano
significa que puedo explicar cada paso. La prueba de que está bien
implementado no es que el código se vea razonable: es que el modelo aprende
una distribución que conozco de antemano (ver tests/domain/test_diffusion.py).
"""

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

RAW = pathlib.Path(__file__).resolve().parent.parent / 'data' / 'german.data'
OUT = (
    pathlib.Path(__file__).resolve().parent.parent
    / 'src' / 'infrastructure' / 'credit' / 'model.npz'
)

# --- Lectura y construcción de los dos ejes -------------------------------
#
# El dataset trae 20 atributos. No los uso todos: proyecto a dos ejes que
# una persona pueda entender, porque el producto es explicativo. La
# proyección es una combinación lineal declarada, no un PCA opaco: si
# alguien pregunta "¿qué significa moverse a la derecha?", hay respuesta.

# Estado de la cuenta corriente. Es el atributo más predictivo del dataset y
# tiene una rareza documentada: "sin cuenta corriente" (A14) correlaciona con
# buen crédito, no con malo — probablemente porque esa gente banca en otro
# lado. Lo codifico como la liquidez observable desde este banco y dejo la
# rareza anotada en vez de esconderla.
CHECKING = {'A11': 0.0, 'A12': 1.0, 'A13': 2.0, 'A14': 3.0}
EMPLOYMENT = {'A71': 0.0, 'A72': 1.0, 'A73': 2.0, 'A74': 3.0, 'A75': 4.0}
SAVINGS = {'A61': 0.0, 'A62': 1.0, 'A63': 2.0, 'A64': 3.0, 'A65': 0.0}
HISTORY = {'A30': 3.0, 'A31': 3.0, 'A32': 2.0, 'A33': 1.0, 'A34': 0.0}
PROPERTY = {'A121': 3.0, 'A122': 2.0, 'A123': 1.0, 'A124': 0.0}
JOB = {'A171': 0.0, 'A172': 1.0, 'A173': 2.0, 'A174': 3.0}


def standardise(column):
    return (column - column.mean()) / column.std()


def load_axes():
    rows = [line.split() for line in RAW.read_text().splitlines() if line.strip()]
    if len(rows) != 1000:
        raise SystemExit(f'Se esperaban 1000 filas, hay {len(rows)}')

    checking = np.array([CHECKING[r[0]] for r in rows])
    duration = np.array([float(r[1]) for r in rows])
    amount = np.array([float(r[4]) for r in rows])
    savings = np.array([SAVINGS[r[5]] for r in rows])
    employment = np.array([EMPLOYMENT[r[6]] for r in rows])
    installment_rate = np.array([float(r[7]) for r in rows])
    residence_since = np.array([float(r[10]) for r in rows])
    prop = np.array([PROPERTY[r[11]] for r in rows])
    history = np.array([HISTORY[r[2]] for r in rows])
    job = np.array([JOB[r[16]] for r in rows])
    good = np.array([1.0 if r[20] == '1' else 0.0 for r in rows])

    # Capacidad: cuánto puede sostener al mes. La cuota mensual implícita del
    # crédito es el proxy directo; la tasa de cuota sobre ingreso disponible
    # resta, porque un porcentaje alto significa menos margen.
    capacity = (
        0.45 * standardise(checking)
        + 0.30 * standardise(np.log(amount / duration))
        + 0.15 * standardise(job)
        - 0.10 * standardise(installment_rate)
    )

    # Estabilidad: cuánto tiempo lleva sosteniendo lo que sostiene.
    stability = (
        0.30 * standardise(history)
        + 0.25 * standardise(savings)
        + 0.20 * standardise(employment)
        - 0.15 * standardise(np.log(duration))
        + 0.05 * standardise(prop)
        + 0.05 * standardise(residence_since)
    )

    points = np.stack([standardise(capacity), standardise(stability)], axis=1)
    return points.astype(np.float64), good


# --- Clasificador ---------------------------------------------------------
#
# Regresión logística sobre los dos ejes, con término cuadrático para que la
# frontera pueda curvarse. Es deliberadamente simple: el clasificador no es
# la parte interesante y un modelo opaco aquí volvería el producto
# indefendible.

def design(x):
    return np.column_stack([
        np.ones(len(x)), x[:, 0], x[:, 1],
        x[:, 0] ** 2, x[:, 1] ** 2, x[:, 0] * x[:, 1],
    ])


def train_classifier(x, y, steps=4000, lr=0.15):
    features = design(x)
    weights = np.zeros(features.shape[1])
    for _ in range(steps):
        prob = 1 / (1 + np.exp(-features @ weights))
        weights -= lr * (features.T @ (prob - y)) / len(y)
    return weights


def qualify_probability(x, weights):
    return 1 / (1 + np.exp(-design(np.atleast_2d(x)) @ weights))


# --- Denoiser: un MLP de dos capas, con backprop a mano -------------------

def time_features(t, total):
    """Codificación sinusoidal del paso de ruido."""
    scaled = (t / total)[:, None]
    frequencies = np.array([1.0, 2.0, 4.0, 8.0])[None, :]
    angles = scaled * frequencies * np.pi
    return np.concatenate([np.sin(angles), np.cos(angles)], axis=1)


class Denoiser:
    """Predice el ruido que se le agregó a un punto. 2 + 8 -> 128 -> 128 -> 2."""

    def __init__(self, hidden=128, seed=7):
        rng = np.random.default_rng(seed)
        scale = lambda a, b: rng.normal(0, np.sqrt(2 / a), (a, b))
        self.w1, self.b1 = scale(10, hidden), np.zeros(hidden)
        self.w2, self.b2 = scale(hidden, hidden), np.zeros(hidden)
        self.w3, self.b3 = scale(hidden, 2), np.zeros(2)

    @property
    def params(self):
        return [self.w1, self.b1, self.w2, self.b2, self.w3, self.b3]

    def forward(self, x, t, total):
        inputs = np.concatenate([x, time_features(t, total)], axis=1)
        h1 = np.tanh(inputs @ self.w1 + self.b1)
        h2 = np.tanh(h1 @ self.w2 + self.b2)
        return h2 @ self.w3 + self.b3, (inputs, h1, h2)

    def backward(self, cache, d_out):
        inputs, h1, h2 = cache
        n = len(inputs)
        g_w3, g_b3 = h2.T @ d_out / n, d_out.mean(axis=0)
        d_h2 = (d_out @ self.w3.T) * (1 - h2 ** 2)
        g_w2, g_b2 = h1.T @ d_h2 / n, d_h2.mean(axis=0)
        d_h1 = (d_h2 @ self.w2.T) * (1 - h1 ** 2)
        g_w1, g_b1 = inputs.T @ d_h1 / n, d_h1.mean(axis=0)
        return [g_w1, g_b1, g_w2, g_b2, g_w3, g_b3]


class Adam:
    def __init__(self, params, lr=2e-3):
        self.lr = lr
        self.m = [np.zeros_like(p) for p in params]
        self.v = [np.zeros_like(p) for p in params]
        self.step_count = 0

    def step(self, params, grads):
        self.step_count += 1
        bias1 = 1 - 0.9 ** self.step_count
        bias2 = 1 - 0.999 ** self.step_count
        for i, (param, grad) in enumerate(zip(params, grads)):
            self.m[i] = 0.9 * self.m[i] + 0.1 * grad
            self.v[i] = 0.999 * self.v[i] + 0.001 * grad ** 2
            param -= self.lr * (self.m[i] / bias1) / (np.sqrt(self.v[i] / bias2) + 1e-8)


def make_schedule(total=200):
    # beta_end=0.06 deja alpha_bar final en 0.002: con 200 pasos, el 0.02
    # habitual de DDPM (pensado para 1000 pasos) no alcanza a destruir la
    # senal, y muestrear desde ruido puro dejaria de ser valido.
    betas = np.linspace(1e-4, 0.06, total)
    alphas = 1 - betas
    return betas, alphas, np.cumprod(alphas)


def train_denoiser(points, total=200, steps=6000, batch=256, seed=7):
    rng = np.random.default_rng(seed)
    _, _, alpha_bar = make_schedule(total)
    model = Denoiser(seed=seed)
    optimiser = Adam(model.params)
    losses = []
    for step in range(steps):
        idx = rng.integers(0, len(points), batch)
        x0 = points[idx]
        t = rng.integers(0, total, batch)
        noise = rng.normal(size=x0.shape)
        a = alpha_bar[t][:, None]
        xt = np.sqrt(a) * x0 + np.sqrt(1 - a) * noise
        predicted, cache = model.forward(xt, t, total)
        error = predicted - noise
        optimiser.step(model.params, model.backward(cache, 2 * error / len(x0)))
        if step % 500 == 0:
            losses.append((step, float((error ** 2).mean())))
    return model, losses


def main():
    points, good = load_axes()
    print(f'{len(points)} perfiles · {good.mean():.0%} con crédito bueno')

    weights = train_classifier(points, good)
    accuracy = ((qualify_probability(points, weights) > 0.5) == good).mean()
    baseline = max(good.mean(), 1 - good.mean())
    print(f'clasificador: {accuracy:.1%} de acierto · clase mayoritaria: {baseline:.1%}')
    if accuracy <= baseline + 0.01:
        print('  AVISO: el clasificador no supera a predecir siempre la clase mayoritaria.')

    model, losses = train_denoiser(points)
    print('difusión: pérdida', ' -> '.join(f'{value:.3f}' for _, value in losses[:: max(1, len(losses) // 5)]))

    # Se guardan también perfiles generados por el propio modelo. Sirven para
    # dos cosas: densifican el mapa (1000 puntos reales se ven ralos) y son la
    # prueba visual de que aprendió la distribución — si se superponen a los
    # reales, la aprendió; si forman otra nube, no.
    from src.infrastructure.credit.diffusion import CreditModel
    engine = CreditModel({
        'w1': model.w1, 'b1': model.b1, 'w2': model.w2, 'b2': model.b2,
        'w3': model.w3, 'b3': model.b3, 'classifier': weights,
        'population': points, 'population_good': good, 'total_steps': 200,
    })
    generated = engine.sample(2500, seed=42)
    inside = np.abs(generated).max(axis=1) < 4
    generated = generated[inside]
    nearest = np.linalg.norm(generated[:, None, :] - points[None, :, :], axis=2).min(axis=1)
    print(f'generados: {len(generated)} · distancia mediana a un perfil real {np.median(nearest):.3f}')

    OUT.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        OUT,
        w1=model.w1, b1=model.b1, w2=model.w2, b2=model.b2, w3=model.w3, b3=model.b3,
        classifier=weights, population=points, population_good=good,
        generated=generated, total_steps=200,
    )
    print(f'guardado en {OUT.relative_to(OUT.parents[4])} ({OUT.stat().st_size / 1024:.0f} KB)')


if __name__ == '__main__':
    sys.exit(main())
