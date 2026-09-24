"""Inferencia del modelo de difusión, en numpy puro.

El entrenamiento vive en `scripts/train_credit_model.py` y se corre a mano.
Aquí solo se carga el artefacto y se ejecuta hacia adelante: cuatro
multiplicaciones de matrices. Por eso el backend no necesita PyTorch.
"""

import pathlib
import threading

import numpy as np

MODEL_PATH = pathlib.Path(__file__).resolve().parent / 'model.npz'

_lock = threading.Lock()
_model = None


class CreditModel:
    def __init__(self, data):
        self.w1, self.b1 = data['w1'], data['b1']
        self.w2, self.b2 = data['w2'], data['b2']
        self.w3, self.b3 = data['w3'], data['b3']
        self.classifier = data['classifier']
        self.population = data['population']
        self.population_good = data['population_good']
        # Perfiles que el modelo inventó. Vacío mientras se entrena.
        self.generated = data['generated'] if 'generated' in data else np.empty((0, 2))
        self.total_steps = int(data['total_steps'])
        # Debe coincidir exactamente con make_schedule() del entrenamiento.
        betas = np.linspace(1e-4, 0.06, self.total_steps)
        self.betas = betas
        self.alphas = 1 - betas
        self.alpha_bar = np.cumprod(self.alphas)

    # --- denoiser ---------------------------------------------------------

    def _time_features(self, t, count):
        scaled = np.full((count, 1), t / self.total_steps)
        frequencies = np.array([1.0, 2.0, 4.0, 8.0])[None, :]
        angles = scaled * frequencies * np.pi
        return np.concatenate([np.sin(angles), np.cos(angles)], axis=1)

    def predict_noise(self, x, t):
        inputs = np.concatenate([x, self._time_features(t, len(x))], axis=1)
        h1 = np.tanh(inputs @ self.w1 + self.b1)
        h2 = np.tanh(h1 @ self.w2 + self.b2)
        return h2 @ self.w3 + self.b3

    def denoise_from(self, x, start_step, rng):
        """Camina la cadena inversa desde `start_step` hasta 0.

        Es la operación que mantiene un punto sobre la variedad de perfiles
        reales: le quita el ruido devolviéndolo a donde la distribución
        aprendida tiene masa.
        """
        for t in range(start_step, -1, -1):
            noise = self.predict_noise(x, t)
            mean = (x - self.betas[t] / np.sqrt(1 - self.alpha_bar[t]) * noise)
            mean = mean / np.sqrt(self.alphas[t])
            if t > 0:
                x = mean + np.sqrt(self.betas[t]) * rng.normal(size=x.shape)
            else:
                x = mean
        return x

    def sample(self, count, seed=0):
        """Genera perfiles nuevos partiendo de ruido puro."""
        rng = np.random.default_rng(seed)
        x = rng.normal(size=(count, 2))
        return self.denoise_from(x, self.total_steps - 1, rng)

    def project_to_manifold(self, x, strength=40, seed=0):
        """Empuja un punto hacia donde vive gente real.

        Le agrega ruido hasta un paso intermedio y lo denoisa de vuelta. Un
        punto que ya estaba sobre la variedad se mueve poco; uno inventado se
        mueve hasta la zona poblada más cercana.
        """
        rng = np.random.default_rng(seed)
        a = self.alpha_bar[strength]
        noisy = np.sqrt(a) * x + np.sqrt(1 - a) * rng.normal(size=x.shape)
        return self.denoise_from(noisy, strength, rng)

    # --- clasificador -----------------------------------------------------

    def qualify_probability(self, x):
        x = np.atleast_2d(x)
        features = np.column_stack([
            np.ones(len(x)), x[:, 0], x[:, 1],
            x[:, 0] ** 2, x[:, 1] ** 2, x[:, 0] * x[:, 1],
        ])
        return 1 / (1 + np.exp(-features @ self.classifier))

    # --- la trayectoria ---------------------------------------------------

    def target_point(self, start):
        """El destino: un perfil que califica, entre los más parecidos al tuyo.

        No busco el que más califica, sino el más cercano que califique con
        holgura. Un destino lejano produce un consejo inalcanzable.
        """
        probabilities = self.qualify_probability(self.population)
        qualifying = self.population[probabilities > 0.72]
        if len(qualifying) == 0:
            qualifying = self.population[probabilities > probabilities.mean()]
        distances = np.linalg.norm(qualifying - start, axis=1)
        nearest = qualifying[np.argsort(distances)[:25]]
        return nearest.mean(axis=0)

    def guided_path(self, start, steps=24, seed=0):
        """Traza el camino desde el punto del usuario hasta uno que califica.

        Interpola hacia el destino, pero en cada paso reproyecta sobre la
        variedad aprendida. Ese reproyectado es lo que hace que el camino se
        curve por donde hay gente real en vez de cortar en línea recta por
        zonas vacías, que es justo lo que haría un contrafactual ingenuo.
        """
        start = np.asarray(start, dtype=float)
        target = self.target_point(start)

        # Primero, la recta entre donde estás y donde quieres llegar.
        alphas = np.linspace(0, 1, steps + 1)[:, None]
        straight = (1 - alphas) * start + alphas * target

        # Luego, cada punto intermedio se reproyecta sobre la variedad. Aquí
        # es donde el camino deja de ser una recta y empieza a pasar por donde
        # de verdad hay gente.
        projected = straight.copy()
        interior = straight[1:-1]
        if len(interior):
            projected[1:-1] = self.project_to_manifold(interior, strength=30, seed=seed)

        # Un camino debe avanzar: si el destino está adelante en un eje, ese
        # eje no retrocede. Sin esto el reproyectado puede sugerir bajar el
        # ahorro a mitad de la ruta, que como consejo no tiene sentido.
        direction = np.sign(target - start)
        for index in range(1, len(projected) - 1):
            for axis in (0, 1):
                if direction[axis] > 0:
                    projected[index, axis] = max(projected[index, axis], projected[index - 1, axis])
                elif direction[axis] < 0:
                    projected[index, axis] = min(projected[index, axis], projected[index - 1, axis])

        # Suavizar va al final, después de forzar la monotonía: al revés, el
        # recorte deja esquinas en ángulo recto que se ven mecánicas. Los
        # extremos no se tocan, son tu punto y el destino.
        smoothed = projected.copy()
        for _ in range(6):
            smoothed[1:-1] = (smoothed[:-2] + 2 * smoothed[1:-1] + smoothed[2:]) / 4

        # El destino es el promedio de un grupo de perfiles cercanos, así que
        # el camino puede pasar por un punto mejor que él y después bajar.
        # Mostrar ese tramo final sería recomendar empeorar: se corta el
        # camino en su mejor punto y se vuelve a repartir en `steps` tramos,
        # para que el deslizador siga recorriéndolo de principio a fin.
        best = int(np.argmax(self.qualify_probability(smoothed)))
        if best >= 2:
            smoothed = _resample(smoothed[: best + 1], steps + 1)

        return smoothed, self.qualify_probability(smoothed)


def _resample(path, count):
    """Reparte `count` puntos a distancia pareja a lo largo de la polilínea."""
    steps = np.linalg.norm(np.diff(path, axis=0), axis=1)
    travelled = np.concatenate([[0.0], np.cumsum(steps)])
    if travelled[-1] == 0:
        return np.repeat(path[:1], count, axis=0)
    wanted = np.linspace(0, travelled[-1], count)
    return np.stack([np.interp(wanted, travelled, path[:, axis]) for axis in (0, 1)], axis=1)


def load_model():
    global _model
    with _lock:
        if _model is None:
            if not MODEL_PATH.exists():
                raise FileNotFoundError(
                    f'Falta {MODEL_PATH.name}. Corre scripts/train_credit_model.py.'
                )
            _model = CreditModel(np.load(MODEL_PATH))
    return _model
