/** La silueta de la casa de Habi, como coordenadas.
 *
 *  La forma está derivada del logo por medidas, no leyendo la imagen: el
 *  archivo es un activo de marca y no se redistribuye. Solo la casa y el
 *  punto — sin el texto, que a tamaño de partícula sería ilegible de todos
 *  modos.
 *
 *  Sistema de coordenadas: ancho de la casa = 1, origen en su centro, y
 *  hacia arriba.
 */

const HALF_WIDTH = 0.5;
const APEX_Y = 0.4755;
const BASE_Y = -0.4755;
/** Donde el techo termina y empiezan los muros. Cae casi en el centro
 *  vertical, igual que en el logo. */
const SHOULDER_Y = 0.024;
const CORNER_RADIUS = 0.095;

const DOT_CENTER = { x: 0.327, y: 0.323 };
const DOT_RADIUS = 0.055;

/** El punto se lleva más partículas de las que le tocarían por área (sería
 *  el 1,3%). Con su proporción real se vería como un puñado de motas sueltas
 *  en vez de un punto. */
const DOT_SHARE = 0.06;

function insideHouse(x: number, y: number): boolean {
  if (y > APEX_Y || y < BASE_Y || Math.abs(x) > HALF_WIDTH) return false;

  if (y >= SHOULDER_Y) {
    // Techo: el ancho se estrecha linealmente hasta el vértice.
    const descended = (APEX_Y - y) / (APEX_Y - SHOULDER_Y);
    return Math.abs(x) <= HALF_WIDTH * descended;
  }

  // Muros, con las dos esquinas de abajo redondeadas.
  const intoCorner = BASE_Y + CORNER_RADIUS - y;
  if (intoCorner <= 0) return true;
  const fromSide = HALF_WIDTH - CORNER_RADIUS - Math.abs(x);
  if (fromSide >= 0) return true;
  return Math.hypot(fromSide, intoCorner) <= CORNER_RADIUS;
}

/** Reparte `count` puntos dentro de la silueta.
 *
 *  Muestreo por rechazo: se tiran puntos en el rectángulo que la contiene y
 *  se descartan los de afuera. Para una forma de esta área es más simple y
 *  más rápido que triangularla, y el `random` inyectado mantiene la
 *  animación idéntica en cada carga.
 */
export function houseSilhouette(count: number, random: () => number): [number, number][] {
  const points: [number, number][] = [];
  const dots = Math.round(count * DOT_SHARE);

  while (points.length < count - dots) {
    const x = (random() - 0.5) * 2 * HALF_WIDTH;
    const y = BASE_Y + random() * (APEX_Y - BASE_Y);
    if (insideHouse(x, y)) points.push([x, y]);
  }

  while (points.length < count) {
    // Raíz cuadrada del radio: sin ella los puntos se apelotonan en el centro
    // del círculo y el borde queda deshilachado.
    const angle = random() * Math.PI * 2;
    const radius = Math.sqrt(random()) * DOT_RADIUS;
    points.push([DOT_CENTER.x + Math.cos(angle) * radius, DOT_CENTER.y + Math.sin(angle) * radius]);
  }

  return points;
}

export function isDotParticle(index: number, count: number): boolean {
  return index >= count - Math.round(count * DOT_SHARE);
}

export const HOUSE_EXTENT = { halfWidth: HALF_WIDTH, apex: APEX_Y, base: BASE_Y };
export const BRAND_PURPLE = '#6100e0';
export const BRAND_CORAL = '#ff5a5a';
