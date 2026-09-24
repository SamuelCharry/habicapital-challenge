import { Link } from 'react-router-dom';
import type { Movement } from '../api/types';
import { Money } from './Money';
import { EmptyState } from './EmptyState';
const dateFormat = new Intl.DateTimeFormat('es-CO', { dateStyle: 'medium', timeStyle: 'short' });
export function MovementList({ movements }: { movements: Movement[] }) {
  if (!movements.length)
    return (
      <EmptyState title="Tu historia empieza aquí">
        <p>Cuando cargues saldo o hagas una transferencia, verás aquí el monto, la persona y el motivo.</p>
      </EmptyState>
    );
  return (
    <ul className="movements">
      {movements.map(item => {
        const deposit = item.operation_type === 'deposit';
        const incoming = item.amount_minor > 0n;
        return (
          <li key={item.operation_id} className={item.shared_expense_id ? 'movement contextual' : 'movement'}>
            <span className={`movement-icon ${incoming ? 'incoming' : ''}`} aria-hidden="true">
              {deposit ? '+' : incoming ? '↙' : '↗'}
            </span>
            <div className="movement-info">
              <strong>
                {deposit ? 'Carga de saldo' : `${incoming ? 'De' : 'Para'} @${item.counterparty_handle}`}
              </strong>
              <span className="muted">
                {deposit ? 'Saldo recibido' : incoming ? 'Transferencia recibida' : 'Transferencia enviada'}
              </span>
              {item.shared_expense_id ? (
                <Link className="context-chip" to={`/expenses/${item.shared_expense_id}`}>
                  <span aria-hidden="true">◈</span> {item.shared_expense_title}{' '}
                  <span aria-hidden="true">↗</span>
                </Link>
              ) : (
                !deposit && <span className="unlinked">Sin gasto asociado</span>
              )}
            </div>
            <div className="movement-value">
              <Money amount={item.amount_minor} className={incoming ? 'positive' : ''} />
              <time dateTime={item.created_at}>{dateFormat.format(new Date(item.created_at))}</time>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
