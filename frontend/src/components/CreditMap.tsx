import { useEffect, useMemo, useRef, useState } from 'react';
import type { CreditPath } from '../api/types';
import { BRAND_CORAL, BRAND_PURPLE, houseSilhouette, isDotParticle } from './creditMapShape';

const NOT_QUALIFYING = [168, 85, 255];
const QUALIFYING = [45, 245, 190];

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
  pointAppears: 3.9,
  pathDraws: 3.5,
  pathDrawn: 4.4,
};

/** Cuándo el mapa queda quieto. El titileo y la deriva se apagan durante los
 *  0,8 s anteriores, así que el último fotograma es igual al anterior y el
 *  bucle puede parar sin salto visible. Antes no paraba nunca: seguía
 *  redibujando 3.500 partículas por fotograma mientras la página estuviera
 *  abierta, y con movimiento reducido repintaba la misma imagen para siempre. */
const CALM_STARTS = 4.4;
const SETTLES_AT = 5.2;

/** Cada cuántos pasos de la ruta hay una estrella de la constelación. */
const STAR_EVERY = 6;

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
};

/** Mezcla los dos acentos alrededor del umbral, sin frontera dura: la frontera
 *  real no es nítida y dibujarla sería mentir. */
function colourFor(probability: number): string {
  const t = Math.min(1, Math.max(0, ((probability - QUALIFIES_AT) / 0.1) * 0.5 + 0.5));
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

export function CreditMap({ path, position }: { path: CreditPath; position: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const startedAt = useRef(performance.now());
  const particlesRef = useRef<Particle[]>([]);

  // Se leía una sola vez al montar, así que cambiar la preferencia del sistema
  // no tenía efecto hasta recargar. Ahora escucha el cambio.
  const [reducedMotion, setReducedMotion] = useState(
    () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false,
  );
  useEffect(() => {
    const query = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    if (!query) return;
    const sync = () => setReducedMotion(query.matches);
    query.addEventListener('change', sync);
    return () => query.removeEventListener('change', sync);
  }, []);

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
        size: generated ? 1.7 : 2.4,
        logoColor: isDotParticle(index, points.length) ? BRAND_CORAL : BRAND_PURPLE,
        dataColor: colourFor(probability),
        dataAlpha: generated ? 0.55 : 1,
      };
    });

    startedAt.current = performance.now();
  }, [path]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let frame = 0;
    const context = canvas.getContext('2d');
    if (!context) return;

    const render = (elapsed: number, seconds: number) => {
      const ratio = window.devicePixelRatio || 1;
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      if (!width) return;
      if (canvas.width !== Math.round(width * ratio)) {
        canvas.width = Math.round(width * ratio);
        canvas.height = Math.round(height * ratio);
      }
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, width, height);

      // El titileo y la deriva se apagan antes del reposo.
      const calm = 1 - between(elapsed, CALM_STARTS, SETTLES_AT);

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

      // Sobre el fondo oscuro las partículas suman luz, como una galaxia.
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

        x += particle.swirl * bulge * houseScale;
        y += Math.sin(particle.phase) * bulge * houseScale * 0.3;

        const drift = calm * settled * Math.sin(seconds * breathe + particle.phase);
        const logoAlpha = isLogoDot(particle) ? 1 : 0.85;
        const base =
          (0.25 + 0.75 * forming) * (particle.dataAlpha + (logoAlpha - particle.dataAlpha) * (1 - settled));
        // Una vez asentadas, las estrellas titilan un poco.
        const twinkle =
          1 - calm * settled * 0.15 * (0.5 + 0.5 * Math.sin(seconds * 1.7 + particle.phase * 5));
        const alpha = base * twinkle;

        context.globalAlpha = Math.min(1, alpha);
        context.fillStyle =
          forming < 0.12
            ? '#8b8a9e'
            : settled > 0.55
              ? particle.dataColor
              : particle.logoColor;
        const size = particle.size + (1 - settled) * 0.6;
        context.fillRect(x + drift, y + drift * 0.6, size, size);
      }
      context.globalCompositeOperation = 'source-over';
      context.globalAlpha = 1;

      if (!path.trajectory.length) return;

      const drawn = between(elapsed, T.pathDraws, T.pathDrawn);
      const eased = drawn < 0.5 ? 2 * drawn * drawn : 1 - Math.pow(-2 * drawn + 2, 2) / 2;
      const screen = path.trajectory.map(waypoint => toData(waypoint.capacity, waypoint.stability));

      if (drawn > 0) {
        // La ruta como constelación: estrellas en los hitos del camino, unidas
        // por trazos rectos que se van dibujando de una a la siguiente.
        const stars = screen.filter((_, index) => index % STAR_EVERY === 0 || index === screen.length - 1);
        const reach = eased * (stars.length - 1);
        context.save();
        context.lineCap = 'round';
        context.strokeStyle = 'rgba(255,255,255,.75)';
        context.lineWidth = 2;
        context.beginPath();
        context.moveTo(stars[0][0], stars[0][1]);
        for (let index = 1; index < stars.length; index++) {
          const t = Math.min(1, reach - (index - 1));
          if (t <= 0) break;
          const [ax, ay] = stars[index - 1];
          const [bx, by] = stars[index];
          context.lineTo(ax + (bx - ax) * t, ay + (by - ay) * t);
        }
        context.stroke();

        context.shadowColor = 'rgba(255,255,255,.9)';
        context.shadowBlur = 18;
        context.fillStyle = '#ffffff';
        stars.forEach(([x, y], index) => {
          const lit = clamp01((reach - index) * 3 + 1);
          if (lit <= 0) return;
          context.globalAlpha = lit * (1 - calm * 0.2 * (0.5 - 0.5 * Math.sin(seconds * 2 + index)));
          context.beginPath();
          context.arc(x, y, index === stars.length - 1 ? 5.5 : 4, 0, Math.PI * 2);
          context.fill();
        });
        context.restore();
      }

      const appeared = between(elapsed, T.pointAppears, T.pointAppears + 0.6);
      if (appeared <= 0) return;

      const index = Math.round((position / 100) * (screen.length - 1));
      const [x, y] = screen[index];

      if (index > 0) {
        const [originPointX, originPointY] = screen[0];
        context.strokeStyle = 'rgba(255,255,255,.5)';
        context.lineWidth = 1;
        context.beginPath();
        context.arc(originPointX, originPointY, 6, 0, Math.PI * 2);
        context.stroke();
      }

      const radius = 36 * appeared;
      const halo = context.createRadialGradient(x, y, 0, x, y, radius);
      halo.addColorStop(0, `rgba(255,255,255,${0.45 * appeared})`);
      halo.addColorStop(1, 'rgba(255,255,255,0)');
      context.fillStyle = halo;
      context.beginPath();
      context.arc(x, y, radius, 0, Math.PI * 2);
      context.fill();
      context.globalAlpha = appeared;
      context.fillStyle = '#ffffff';
      context.beginPath();
      context.arc(x, y, 7.5, 0, Math.PI * 2);
      context.fill();
      context.globalAlpha = 1;
    };

    const elapsedAt = (now: number) =>
      reducedMotion ? SETTLES_AT : (now - startedAt.current) / 1000;

    const tick = (now: number) => {
      render(elapsedAt(now), now / 1000);
      // Con movimiento reducido se dibuja un solo fotograma; si no, se dibuja
      // hasta el reposo y después el mapa se queda quieto.
      if (elapsedAt(now) < SETTLES_AT) frame = requestAnimationFrame(tick);
      else frame = 0;
    };

    frame = requestAnimationFrame(tick);

    // El bucle ya no está corriendo para recoger un cambio de tamaño, así que
    // hay que repintar explícitamente.
    const repaint = () => {
      if (frame) return;
      frame = requestAnimationFrame(now => {
        frame = 0;
        render(elapsedAt(now), now / 1000);
      });
    };
    const observer = new ResizeObserver(repaint);
    observer.observe(canvas);

    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
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
