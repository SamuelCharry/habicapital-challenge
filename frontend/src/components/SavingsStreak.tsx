import { Link } from 'react-router-dom';
import type { CreditSummary } from '../api/types';
import { Money } from './Money';

/** La bisagra del producto: convierte el historial de la billetera en las tres
 *  cifras que un originador hipotecario quiere ver. */
export function SavingsStreak({ summary }: { summary: CreditSummary }) {
  return (
    <section className="streak" aria-label="Tu constancia de ahorro">
      <div>
        <span>de constancia</span>
        <strong>
          {summary.months_consistent}
          {summary.months_consistent === 1 ? ' mes' : ' meses'}
        </strong>
      </div>
      <div>
        <span>ahorro promedio</span>
        <strong>
          <Money amount={summary.monthly_savings_minor} />
        </strong>
      </div>
      <div>
        <span>cumplimiento</span>
        <strong className={summary.compliance_ratio === null ? 'muted' : 'good'}>
          {summary.compliance_ratio === null
            ? '—'
            : `${Math.round(summary.compliance_ratio * 100)}%`}
        </strong>
      </div>
      <Link to="/ruta">
        Tu comportamiento ya cuenta para un crédito de vivienda{' '}
        <span aria-hidden="true">→</span>
      </Link>
    </section>
  );
}
