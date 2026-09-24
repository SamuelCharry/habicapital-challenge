const pesos = new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0 });
export function formatMoney(minor: bigint): string {
  const absolute = minor < 0n ? -minor : minor;
  const cents = absolute % 100n;
  return `${minor < 0n ? '−' : ''}$ ${pesos.format(absolute / 100n)}${cents ? `,${cents.toString().padStart(2, '0')}` : ''}`;
}

export function people(count: number): string {
  return count === 1 ? '1 persona' : `${count} personas`;
}
