import { useEffect, useMemo, useRef } from 'react';
import type { CreditPath } from '../api/types';
import { BRAND_CORAL, BRAND_PURPLE, houseSilhouette, isDotParticle } from './creditMapShape';

const NOT_QUALIFYING = [123, 82, 224];
const QUALIFYING = [20, 184, 166];

// El umbral que el producto considera "califica". El degradado se centra aquí,
// no en 0.5: si se centrara en 0.5 casi toda la nube saldría turquesa, porque
// el 70% del dataset tiene buen crédito, y el mapa diría que casi todo el mundo
// califica.
const QUALIFIES_AT = 0.72;

// La secuencia completa. Las partículas salen de ruido, se condensan en la casa
// de Habi, la sostienen, y después se disuelven para reordenarse en los
// perfiles reales. El primer tramo es marca; el segundo es el producto.
// Toda la secuencia cabe en 4,4 segundos. La versión anterior duraba casi
// ocho y se hacía larga: en una demo de cinco minutos, ocho segundos mirando
// partículas es demasiado.
const T = {
  houseStarts: 0.25,
  houseFormed: 1.7,
  houseHolds: 2.1,
  dataFormed: 3.3,
  // Segundo momento de difusión: las partículas más cercanas a la ruta se
  // desprenden de la nube y se alinean sobre ella.
  roadStarts: 3.4,
  roadFormed: 4.4,
  pointAppears: 3.9,
  pathDraws: 3.5,
  pathDrawn: 4.4,
};

/** Cuántas partículas forman el corredor. Con menos no se lee como camino;
 *  con muchas más, la nube se vacía y deja de haber mapa. */
const ROAD_PARTICLES = 520;

type Particle = {
  noiseX: number;
  noiseY: number;
  houseX: number;
  houseY: number;
  dataX: number;
  dataY: number;
  /** Desvío lateral durante la disolución, para que la transición no parezca
   *  un bloque rígido moviéndose. */
  swirl: number;
  phase: number;
  size: number;
  logoColor: string;
  dataColor: string;
  dataAlpha: number;
  /** Posición sobre la ruta, si esta partícula forma parte del corredor. */
  roadX: number | null;
  roadY: number | null;
  /** Color según la probabilidad de calificar en ese punto del camino. */
  roadColor: string;
};

/** Mezcla los dos acentos alrededor del umbral, sin frontera dura: la frontera
 *  real no es nítida y dibujarla sería mentir. */
function colourFor(probability: number): string {
  const t = Math.min(1, Math.max(0, ((probability - QUALIFIES_AT) / 0.3) * 0.5 + 0.5));
  const channels = NOT_QUALIFYING.map((value, index) => Math.round(value + (QUALIFYING[index] - value) * t));
  return `rgb(${channels.join(',')})`;
}

/** Posiciones deterministas, para que la animación sea idéntica en cada carga
 *  y la demo se pueda repetir. */
function scatter(seed: number): () => number {
  let state = seed;
  return () => (state = (state * 16807) % 2147483647) / 2147483647;
}

const isLogoDot = (p: { logoColor: string }) => p.logoColor === BRAND_CORAL;
const clamp01 = (t: number) => Math.min(1, Math.max(0, t));
const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);
const between = (value: number, from: number, to: number) => clamp01((value - from) / (to - from));

/** Elige las partículas que formarán el corredor y les da su sitio sobre la
 *  ruta.
 *
 *  Se toman las más cercanas al camino, no unas cualesquiera: así el corredor
 *  está hecho de los perfiles reales por los que tu ruta pasa, y la frase
 *  "el camino pasa por gente que existe" sigue siendo cierta al pie de la
 *  letra. Después se reparten a lo largo del recorrido, con un desvío
 *  perpendicular pequeño que le da grosor y textura.
 */
function assignRoad(particles: Particle[], trajectory: CreditPath['trajectory'], random: () => number) {
  if (trajectory.length < 2) return;
  const route = trajectory.map(w => [w.capacity, w.stability] as const);

  const distanceToRoute = (x: number, y: number) => {
    let best = Infinity;
    for (let i = 0; i < route.length - 1; i++) {
      const [ax, ay] = route[i];
      const [bx, by] = route[i + 1];
      const dx = bx - ax;
      const dy = by - ay;
      const lengthSquared = dx * dx + dy * dy || 1;
      const t = Math.max(0, Math.min(1, ((x - ax) * dx + (y - ay) * dy) / lengthSquared));
      best = Math.min(best, Math.hypot(x - (ax + dx * t), y - (ay + dy * t)));
    }
    return best;
  };

  const chosen = particles
    .map((particle, index) => ({ index, distance: distanceToRoute(particle.dataX, particle.dataY) }))
    .sort((a, b) => a.distance - b.distance)
    .slice(0, Math.min(ROAD_PARTICLES, particles.length));

  chosen.forEach(({ index }, rank) => {
    const along = (rank / Math.max(1, chosen.length - 1)) * (route.length - 1);
    const segment = Math.min(route.length - 2, Math.floor(along));
    const t = along - segment;
    const [ax, ay] = route[segment];
    const [bx, by] = route[segment + 1];
    const dx = bx - ax;
    const dy = by - ay;
    const length = Math.hypot(dx, dy) || 1;
    // Desvío perpendicular: sin él, el corredor sería una línea de un píxel.
    const offset = (random() - 0.5) * 0.09;
    const particle = particles[index];
    particle.roadX = ax + dx * t - (dy / length) * offset;
    particle.roadY = ay + dy * t + (dx / length) * offset;

    // El corredor se tiñe con la probabilidad real de cada punto del camino,
    // así que arranca morado —donde aún no calificas— y termina turquesa.
    // El cruce del umbral se ve, en vez de haber que explicarlo.
    const probability =
      trajectory[segment].qualify_probability * (1 - t) + trajectory[segment + 1].qualify_probability * t;
    particle.roadColor = colourFor(probability);
  });
}

export function CreditMap({ path, position }: { path: CreditPath; position: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const startedAt = useRef(performance.now());
  const particlesRef = useRef<Particle[]>([]);

  const reducedMotion = useMemo(
    () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false,
    [],
  );

  /** El encuadre sale de los datos, pero por percentiles y no por el mínimo y
   *  el máximo absolutos: con esos, un solo perfil extremo encoge todo lo
   *  demás y el mapa se ve desde muy lejos. La trayectoria entera se fuerza a
   *  caber, porque ahí sí no se puede recortar nada. */
  const extent = useMemo(() => {
    const cloud = [...path.population, ...path.generated];
    if (!cloud.length) return { centerX: 0, centerY: 0, halfSpan: 1 };

    const span = (values: number[], low: number, high: number) => {
      const sorted = [...values].sort((a, b) => a - b);
      const at = (q: number) => sorted[Math.min(sorted.length - 1, Math.floor(q * sorted.length))];
      return [at(low), at(high)] as const;
    };
    // 4/96: el 8% de los perfiles más extremos queda fuera de cuadro a
    // propósito. Son justo los que hacían que todo lo demás se viera diminuto,
    // y el lienzo los recorta sin que se note.
    let [minX, maxX] = span(
      cloud.map(p => p[0]),
      0.04,
      0.96,
    );
    let [minY, maxY] = span(
      cloud.map(p => p[1]),
      0.04,
      0.96,
    );

    for (const waypoint of path.trajectory) {
      minX = Math.min(minX, waypoint.capacity);
      maxX = Math.max(maxX, waypoint.capacity);
      minY = Math.min(minY, waypoint.stability);
      maxY = Math.max(maxY, waypoint.stability);
    }
    return {
      centerX: (minX + maxX) / 2,
      centerY: (minY + maxY) / 2,
      halfSpan: Math.max(maxX - minX, maxY - minY) / 2 || 1,
    };
  }, [path]);

  useEffect(() => {
    const random = scatter(11);
    const points = [...path.generated, ...path.population];
    const house = houseSilhouette(points.length, scatter(29));

    particlesRef.current = points.map(([x, y, probability], index) => {
      const generated = index < path.generated.length;
      return {
        noiseX: (random() - 0.5) * 2.6,
        noiseY: (random() - 0.5) * 2.6,
        houseX: house[index][0],
        houseY: house[index][1],
        dataX: x,
        dataY: y,
        swirl: (random() - 0.5) * 0.5,
        phase: random() * Math.PI * 2,
        // Los generados van más tenues y más pequeños: el mapa distingue lo
        // observado de lo inferido en vez de mezclarlos sin decirlo.
        size: generated ? 1.2 : 1.8,
        logoColor: isDotParticle(index, points.length) ? BRAND_CORAL : BRAND_PURPLE,
        dataColor: colourFor(probability),
        dataAlpha: generated ? 0.16 : 0.8,
        roadX: null,
        roadY: null,
        roadColor: '',
      };
    });

    assignRoad(particlesRef.current, path.trajectory, scatter(53));
    startedAt.current = performance.now();
  }, [path]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let frame = 0;

    const draw = (now: number) => {
      frame = requestAnimationFrame(draw);
      const ratio = window.devicePixelRatio || 1;
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      if (!width) return;
      if (canvas.width !== Math.round(width * ratio)) {
        canvas.width = Math.round(width * ratio);
        canvas.height = Math.round(height * ratio);
      }
      const context = canvas.getContext('2d');
      if (!context) return;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, width, height);

      // Siete segundos de animación no pueden ser obligatorios.
      const elapsed = reducedMotion ? 99 : (now - startedAt.current) / 1000;
      const seconds = now / 1000;

      const inset = Math.min(width, height) * 0.05;
      const dataScale = (Math.min(width, height) - inset * 2) / (extent.halfSpan * 2);
      // El logo se ajusta al lado menor del lienzo, no a la altura: si no,
      // en una ventana baja la casa se sale por abajo.
      const houseScale = (Math.min(width, height) - inset * 2) / 1.05;
      const originX = width / 2;
      const originY = height / 2;

      const toHouse = (x: number, y: number): [number, number] => [
        originX + x * houseScale,
        originY - y * houseScale,
      ];
      const toData = (x: number, y: number): [number, number] => [
        originX + (x - extent.centerX) * dataScale,
        originY - (y - extent.centerY) * dataScale,
      ];

      const forming = easeOut(between(elapsed, T.houseStarts, T.houseFormed));
      const dissolving = between(elapsed, T.houseHolds, T.dataFormed);
      const settled = easeOut(dissolving);
      // La disolución abulta hacia afuera a mitad de camino: sin eso el paso de
      // la casa a los datos parece una diapositiva, no partículas sueltas.
      const bulge = Math.sin(dissolving * Math.PI);
      // El corredor: segundo momento de ruido que se vuelve estructura.
      const paving = easeOut(between(elapsed, T.roadStarts, T.roadFormed));

      context.globalCompositeOperation = 'lighter';
      const breathe = (Math.PI * 2) / 8;
      for (const particle of particlesRef.current) {
        const [noiseX, noiseY] = toHouse(particle.noiseX, particle.noiseY);
        const [houseX, houseY] = toHouse(particle.houseX, particle.houseY);
        const [dataX, dataY] = toData(particle.dataX, particle.dataY);

        const fromX = noiseX + (houseX - noiseX) * forming;
        const fromY = noiseY + (houseY - noiseY) * forming;
        let x = fromX + (dataX - fromX) * settled;
        let y = fromY + (dataY - fromY) * settled;

        const onRoad = particle.roadX !== null && paving > 0;
        if (onRoad) {
          const [roadX, roadY] = toData(particle.roadX!, particle.roadY!);
          x += (roadX - x) * paving;
          y += (roadY - y) * paving;
        }
        x += particle.swirl * bulge * houseScale;
        y += Math.sin(particle.phase) * bulge * houseScale * 0.3;

        const drift = settled * Math.sin(seconds * breathe + particle.phase);
        const logoAlpha = isLogoDot(particle) ? 1 : 0.85;
        const base =
          (0.25 + 0.75 * forming) * (particle.dataAlpha + (logoAlpha - particle.dataAlpha) * (1 - settled));
        // Las del corredor se encienden a medida que se colocan: es lo que lo
        // hace legible como camino y no como una franja algo más densa.
        const alpha = onRoad ? base + (1 - base) * paving : base;

        context.globalAlpha = Math.min(1, alpha);
        context.fillStyle =
          forming < 0.12
            ? '#8b8a9e'
            : onRoad && paving > 0.5
              ? particle.roadColor
              : settled > 0.55
                ? particle.dataColor
                : particle.logoColor;
        const size = particle.size + (1 - settled) * 0.6 + (onRoad ? paving * 0.5 : 0);
        context.fillRect(x + drift, y + drift * 0.6, size, size);
      }
      context.globalCompositeOperation = 'source-over';
      context.globalAlpha = 1;

      if (!path.trajectory.length) return;

      const drawn = between(elapsed, T.pathDraws, T.pathDrawn);
      const eased = drawn < 0.5 ? 2 * drawn * drawn : 1 - Math.pow(-2 * drawn + 2, 2) / 2;
      const screen = path.trajectory.map(waypoint => toData(waypoint.capacity, waypoint.stability));

      if (drawn > 0) {
        const upTo = Math.max(2, Math.floor(eased * (screen.length - 1)) + 1);
        context.save();
        context.lineCap = 'round';
        context.lineJoin = 'round';
        // Con el corredor de partículas dibujado, la línea pasa a ser un
        // hilo que lo guía, no el protagonista: si se deja gruesa, tapa las
        // partículas que acaban de colocarse.
        context.shadowColor = 'rgba(255,255,255,.6)';
        context.shadowBlur = 10;
        context.strokeStyle = `rgba(255,255,255,${0.85 - paving * 0.45})`;
        context.lineWidth = 2.5 - paving;
        context.beginPath();
        screen.slice(0, upTo).forEach(([x, y], index) => {
          if (index) context.lineTo(x, y);
          else context.moveTo(x, y);
        });
        context.stroke();
        context.restore();

        // Hitos cada seis pasos: dan sensación de recorrido por etapas en vez
        // de una línea continua sin referencias.
        context.fillStyle = 'rgba(242,240,248,.55)';
        for (let index = 6; index < upTo; index += 6) {
          context.beginPath();
          context.arc(screen[index][0], screen[index][1], 2, 0, Math.PI * 2);
          context.fill();
        }
      }

      const appeared = between(elapsed, T.pointAppears, T.pointAppears + 0.6);
      if (appeared <= 0) return;

      const index = Math.round((position / 100) * (screen.length - 1));
      const [x, y] = screen[index];

      if (index > 0) {
        const [originPointX, originPointY] = screen[0];
        context.strokeStyle = 'rgba(242,240,248,.45)';
        context.lineWidth = 1;
        context.beginPath();
        context.arc(originPointX, originPointY, 3.5, 0, Math.PI * 2);
        context.stroke();
      }

      const radius = 24 * appeared;
      const halo = context.createRadialGradient(x, y, 0, x, y, radius);
      halo.addColorStop(0, `rgba(255,255,255,${0.55 * appeared})`);
      halo.addColorStop(1, 'rgba(255,255,255,0)');
      context.fillStyle = halo;
      context.beginPath();
      context.arc(x, y, radius, 0, Math.PI * 2);
      context.fill();
      context.globalAlpha = appeared;
      context.fillStyle = '#fff';
      context.beginPath();
      context.arc(x, y, 4, 0, Math.PI * 2);
      context.fill();
      context.globalAlpha = 1;
    };

    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, [path, position, extent, reducedMotion]);

  return (
    <div className="credit-map">
      <canvas
        ref={canvasRef}
        role="img"
        aria-label={
          path.trajectory.length
            ? 'Mapa de perfiles crediticios con tu posición y la ruta hacia el grupo que califica.'
            : 'Mapa de perfiles crediticios.'
        }
      />
      <div className="credit-legend">
        <span>
          <i style={{ background: colourFor(0.4) }} aria-hidden="true" />
          Aún no califica
        </span>
        <span>
          <i style={{ background: colourFor(1) }} aria-hidden="true" />
          Califica
        </span>
      </div>
    </div>
  );
}
