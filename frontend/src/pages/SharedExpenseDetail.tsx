import { useCallback } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { useActiveAccount } from '../session/ActiveAccount';
import { useLoad } from './useLoad';
import { Card } from '../components/Card';
import { Money } from '../components/Money';
import { Avatar } from '../components/Avatar';
import { MovementList } from '../components/MovementList';
import { EmptyState } from '../components/EmptyState';
import { ErrorBanner } from '../components/ErrorBanner';
import { Spinner } from '../components/Spinner';
import { people } from '../utils/money';
export default function SharedExpenseDetail() {
  const { expenseId = '' } = useParams();
  const { active } = useActiveAccount();
  const load = useCallback(async () => {
    const expense = await api.expense(expenseId);
    // The payer's history has one incoming entry per linked transfer, no duplicates.
    const history = await api.history(expense.payer);
    return { expense, movements: history.filter(item => item.shared_expense_id === expenseId) };
  }, [expenseId]);
  const { data, loading, error, retry } = useLoad(load);
  if (loading) return <Spinner />;
  if (error) return <ErrorBanner message={error} retry={retry} />;
  if (!data) return null;
  const { expense, movements } = data;
  const payer = expense.participants.find(p => p.account_id === expense.payer);
  const me = expense.participants.find(p => p.account_id === active!.id);
  return (
    <>
      <Link className="back-link" to="/">
        <span aria-hidden="true">←</span> Volver al inicio
      </Link>
      <div className="page-heading">
        <div>
          <h1>{expense.title}</h1>
          <p>
            Pagó {payer?.display_name} · {people(expense.participants.length)}
          </p>
        </div>
        <span className={`badge ${expense.settled ? 'settled' : ''}`}>
          {expense.settled ? 'Gasto saldado' : 'Por completar'}
        </span>
      </div>
      <div className="overview-grid">
        <Card>
          <p className="eyebrow">TOTAL DEL GASTO</p>
          <Money className="detail-total" amount={expense.total_minor} />
          <p>Dividido en partes iguales</p>
        </Card>
        <Card className="context-card">
          <p className="eyebrow">PENDIENTE DEL GRUPO</p>
          <Money className="detail-total" amount={expense.outstanding_total_minor} />
          <p>
            {expense.settled
              ? 'Todas las personas cubrieron su parte.'
              : 'Cada pago vinculado actualiza esta cuenta.'}
          </p>
          {me && me.account_id !== expense.payer && !me.settled && (
            <Link className="button" to={`/transfer?expense=${expense.id}`}>
              Pagar mi parte <span aria-hidden="true">↗</span>
            </Link>
          )}
        </Card>
      </div>
      <Card>
        <div className="section-heading">
          <h2>Las cuentas, persona a persona</h2>
        </div>
        {!expense.participants.length ? (
          <EmptyState title="No hay participantes">
            <p>Este gasto todavía no tiene personas asociadas.</p>
          </EmptyState>
        ) : (
          <table className="participants-table">
            <thead>
              <tr>
                <th>Persona</th>
                <th>Su parte</th>
                <th>Pagado</th>
                <th>Pendiente</th>
              </tr>
            </thead>
            <tbody>
              {expense.participants.map(person => (
                <tr key={person.account_id}>
                  <td>
                    <div className="person">
                      <Avatar name={person.display_name} />
                      <div>
                        <strong>{person.display_name}</strong>
                        <small>
                          {person.account_id === expense.payer
                            ? 'Pagó la cuenta · parte cubierta'
                            : `@${person.handle}`}
                        </small>
                        <span className={`badge ${person.settled ? 'settled' : ''}`}>
                          {person.settled ? 'Al día' : 'Pendiente'}
                        </span>
                      </div>
                    </div>
                  </td>
                  <td data-label="Su parte">
                    <Money amount={person.share_minor} />
                  </td>
                  <td data-label="Pagado">
                    <Money amount={person.paid_minor} />
                    {person.excess_minor > 0n && (
                      <small>
                        Excedente: <Money amount={person.excess_minor} />
                      </small>
                    )}
                  </td>
                  <td data-label="Pendiente">
                    <Money amount={person.outstanding_minor} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      <Card>
        <div className="section-heading">
          <div>
            <h2>Pagos de este gasto</h2>
            <p>Recibidos por {payer?.display_name}</p>
          </div>
          <span className="context-chip"><span aria-hidden="true">◈</span> {expense.title}</span>
        </div>
        {movements.length ? (
          <MovementList movements={movements} />
        ) : (
          <EmptyState title="El primer pago está por llegar">
            <p>
              Las transferencias vinculadas a este gasto aparecerán aquí. La parte de quien pagó ya está
              cubierta.
            </p>
          </EmptyState>
        )}
      </Card>
    </>
  );
}
