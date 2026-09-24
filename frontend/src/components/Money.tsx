import { formatMoney } from '../utils/money';
export function Money({ amount, className = '' }: { amount: bigint; className?: string }) {
  return <span className={`money ${className}`}>{formatMoney(amount)}</span>;
}
