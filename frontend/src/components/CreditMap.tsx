import { useEffect, useRef } from 'react';
import type { CreditPath } from '../api/types';

const NOT_QUALIFYING = [123, 82, 224];
const QUALIFYING = [20, 184, 166];

// La condensación dura tres segundos. Más corto se pierde; más largo aburre.
const SETTLE_SECONDS = 3;
const SETTLE_DELAY = 0.4;
const POINT_APPEARS_AT = 3.4;
const PATH_DRAWS_AT = 4;

type Rendered = {
  x: number;
  y: number;
  fromX: number;
  fromY: number;
  phase: number;
  size: number;
  color: string;
  /** Los generados van más tenues: el mapa distingue lo observado de lo
   *  inferido en vez de mezclarlos sin decirlo. */
  alpha: number;
};

// El umbral que el producto considera "califica". El degradado se centra
// aquí, no en 0.5: si se centrara en 0.5 casi toda la nube saldría turquesa,
// porque el 70% del dataset tiene buen crédito, y el mapa diría que casi
// todo el mundo califica.
const QUALIFIES_AT = 0.72;

/** Mezcla los dos acentos alrededor del umbral, sin frontera dura: la
 *  frontera real no es nítida y dibujarla sería mentir. */
function colourFor(probability: number): string {
  const t = Math.min(1, Math.max(0, ((probability - QUALIFIES_AT) / 0.3) * 0.5 + 0.5));
  const channels = NOT_QUALIFYING.map((value, index) =>
    Math.round(value + (QUALIFYING[index] - value) * t),
  );
  return `rgb(${channels.join(',')})`;
}

/** Posiciones de partida deterministas, para que la animación sea idéntica en
 *  cada carga y la demo se pueda repetir. */
function scatter(seed: number): () => number {
  let state = seed;
  return () => (state = (state * 16807) % 2147483647) / 2147483647;
}

export function CreditMap({ path, position }: { path: CreditPath; position: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const startedAt = useRef(performance.now());
  const pointsRef = useRef<Rendered[]>([]);

  useEffect(() => {
    const random = scatter(11);
    const build = (
      points: [number, number, number][],
      alpha: number,
      size: number,
    ): Rendered[] =>
      points.map(([x, y, probability]) => ({
        x,
        y,
        fromX: (random() - 0.5) * 7,
        fromY: (random() - 0.5) * 7,
        phase: random() * Math.PI * 2,
        size,
        color: colourFor(probability),
        alpha,
      }));
    pointsRef.current = [
      ...build(path.generated, 0.16, 1.2),
      ...build(path.population, 0.8, 1.8),
    ];
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

      const elapsed = (now - startedAt.current) / 1000;
      const seconds = now / 1000;
      const raw = Math.min(1, Math.max(0, (elapsed - SETTLE_DELAY) / SETTLE_SECONDS));
      // Desaceleración: rápido al principio, lento al final, como algo que
      // se asienta.
      const settled = 1 - Math.pow(1 - raw, 3);

      // La población estandarizada vive casi toda dentro de ±2.5.
      const bounds = 2.2;
      const scale = Math.min(width, height) / (bounds * 2);
      const originX = width / 2;
      const originY = height / 2;
      const toScreenX = (value: number) => originX + value * scale;
      const toScreenY = (value: number) => originY - value * scale;

      // Mezcla aditiva: donde se acumulan puntos el color satura solo, sin
      // que haya que dibujar contornos ni calcular densidad.
      context.globalCompositeOperation = 'lighter';
      const breathe = (Math.PI * 2) / 8;
      for (const point of pointsRef.current) {
        const x = point.fromX + (point.x - point.fromX) * settled;
        const y = point.fromY + (point.y - point.fromY) * settled;
        const driftX = Math.sin(seconds * breathe + point.phase) * settled;
        const driftY = Math.cos(seconds * breathe + point.phase * 1.3) * settled;
        context.globalAlpha = point.alpha * (0.35 + 0.65 * settled);
        context.fillStyle = settled < 0.15 ? '#8b8a9e' : point.color;
        context.fillRect(toScreenX(x) + driftX, toScreenY(y) + driftY, point.size, point.size);
      }
      context.globalCompositeOperation = 'source-over';
      context.globalAlpha = 1;

      if (!path.trajectory.length) return;

      const drawn = Math.min(1, Math.max(0, (elapsed - PATH_DRAWS_AT) / 1.2));
      const eased = drawn < 0.5 ? 2 * drawn * drawn : 1 - Math.pow(-2 * drawn + 2, 2) / 2;
      if (drawn > 0) {
        const upTo = Math.max(2, Math.floor(eased * (path.trajectory.length - 1)) + 1);
        context.save();
        context.lineCap = 'round';
        context.lineJoin = 'round';
        context.shadowColor = 'rgba(255,255,255,.8)';
        context.shadowBlur = 10;
        context.strokeStyle = 'rgba(255,255,255,.9)';
        context.lineWidth = 1.5;
        context.beginPath();
        path.trajectory.slice(0, upTo).forEach((waypoint, index) => {
          const x = toScreenX(waypoint.capacity);
          const y = toScreenY(waypoint.stability);
          if (index) context.lineTo(x, y);
          else context.moveTo(x, y);
        });
        context.stroke();
        context.restore();
      }

      const appeared = Math.min(1, Math.max(0, (elapsed - POINT_APPEARS_AT) / 0.6));
      if (appeared <= 0) return;
      const index = Math.round((position / 100) * (path.trajectory.length - 1));
      const current = path.trajectory[index];
      const x = toScreenX(current.capacity);
      const y = toScreenY(current.stability);

      if (index > 0) {
        const origin = path.trajectory[0];
        context.strokeStyle = 'rgba(242,240,248,.4)';
        context.lineWidth = 1;
        context.beginPath();
        context.arc(toScreenX(origin.capacity), toScreenY(origin.stability), 3, 0, Math.PI * 2);
        context.stroke();
      }

      const radius = 22 * appeared;
      const halo = context.createRadialGradient(x, y, 0, x, y, radius);
      halo.addColorStop(0, `rgba(255,255,255,${0.5 * appeared})`);
      halo.addColorStop(1, 'rgba(255,255,255,0)');
      context.fillStyle = halo;
      context.beginPath();
      context.arc(x, y, radius, 0, Math.PI * 2);
      context.fill();
      context.globalAlpha = appeared;
      context.fillStyle = '#fff';
      context.beginPath();
      context.arc(x, y, 3.5, 0, Math.PI * 2);
      context.fill();
      context.globalAlpha = 1;
    };

    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, [path, position]);

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
