import { useEffect, useRef } from 'react';

/** Polvo de estrellas detrás del saludo del inicio: el mismo lenguaje de la
 *  galaxia de Tu ruta, pero discreto, para que no compita con el saldo. */
export function HeroParticles() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;

    // Semilla fija: las estrellas caen en el mismo sitio en cada carga.
    let seed = 7;
    const random = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    const stars = Array.from({ length: 170 }, () => ({
      x: random(),
      y: random(),
      size: 0.6 + random() * 1.6,
      alpha: 0.25 + random() * 0.55,
      phase: random() * Math.PI * 2,
      speed: 0.004 + random() * 0.01,
    }));

    let frame = 0;
    const draw = (now: number) => {
      const ratio = window.devicePixelRatio || 1;
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      if (width && canvas.width !== Math.round(width * ratio)) {
        canvas.width = Math.round(width * ratio);
        canvas.height = Math.round(height * ratio);
      }
      const context = canvas.getContext('2d');
      if (context && width) {
        context.setTransform(ratio, 0, 0, ratio, 0, 0);
        context.clearRect(0, 0, width, height);
        const seconds = reduced ? 0 : now / 1000;
        context.fillStyle = '#ffffff';
        for (const star of stars) {
          // Deriva lenta hacia la derecha, con vuelta al inicio al salir.
          const x = ((star.x + seconds * star.speed) % 1) * width;
          const y = star.y * height;
          const twinkle = 0.65 + 0.35 * Math.sin(seconds * 1.5 + star.phase);
          context.globalAlpha = star.alpha * twinkle;
          context.beginPath();
          context.arc(x, y, star.size, 0, Math.PI * 2);
          context.fill();
        }
        context.globalAlpha = 1;
      }
      if (!reduced) frame = requestAnimationFrame(draw);
    };
    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, []);

  return <canvas ref={canvasRef} className="hero-particles" aria-hidden="true" />;
}
