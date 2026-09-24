import { useCallback } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { useActiveAccount } from '../session/ActiveAccount';
import { useLoad } from './useLoad';
import { Card } from '../components/Card';
import { Money } from '../components/Money';
import { MovementList } from '../components/MovementList';
import { EmptyState } from '../components/EmptyState';
import { ErrorBanner } from '../components/ErrorBanner';
import { Spinner } from '../components/Spinner';
import { people } from '../utils/money';
import { SavingsStreak } from '../components/SavingsStreak';

export default function Dashboard() {
  const { active } = useActiveAccount();
  const id = active!.id;
  const load = useCallback(async () => {
    const [balance, history, expenses, summary] = await Promise.all([
      api.balance(id),
      api.history(id),
      api.expenses(id),
      api.creditProfile(id),
    ]);
    return { balance, history, expenses, summary };
  }, [id]);
  const { data, loading, error, retry } = useLoad(load);
  return (
    <>
      <section className="hero">
        <div>
          <p className="eyebrow">TU DINERO, CON CONTEXTO</p>
          <h1>Hola, {active!.display_name.split(' ')[0]}.</h1>
          <p>Las cuentas claras. Los planes, compartidos.</p>
        </div>
        <div className="hero-balance">
          <span>Saldo disponible · @{active!.handle}</span>
          {data && <Money className="balance" amount={data.balance.balance_minor} />}
          <Link className="button light" to="/transfer">
            Transferir dinero
          </Link>
        </div>
      </section>
      {loading ? (
        <Spinner />
      ) : error ? (
        <ErrorBanner message={error} retry={retry} />
      ) : (
        data && (
          <>
            <SavingsStreak summary={data.summary} />
            <div className="overview-grid single">
              <Card className="context-card">
                <span className="context-symbol" aria-hidden="true">
                  ◈
                </span>
                <p className="eyebrow">MÁS QUE UNA TRANSFERENCIA</p>
                <h2>
                  Cada pago tiene
                  <br />
                  una historia.
                </h2>
                <p>Reúne un gasto, reparte las cuentas y descubre quién ya puso su parte.</p>
                <Link className="text-link" to="/expenses/new">
                  Crear un gasto compartido <span aria-hidden="true">→</span>
                </Link>
              </Card>
            </div>
            <div className="dashboard-grid">
              <Card>
                <div className="section-heading">
                  <h2>Actividad reciente</h2>
                  <Link to="/history">Ver todo →</Link>
                </div>
                <MovementList movements={data.history.slice(0, 5)} />
              </Card>
              <Card>
                <div className="section-heading">
                  <h2>Gastos compartidos</h2>
                  <Link to="/expenses/new" aria-label="Crear gasto compartido">
                    ＋
                  </Link>
                </div>
                {!data.expenses.length ? (
                  <EmptyState title="Un plan, varias personas">
                    <p>Crea tu primer gasto y lleva las cuentas de lo que comparten.</p>
                    <Link to="/expenses/new">Crear un gasto →</Link>
                  </EmptyState>
                ) : (
                  <ul className="expense-list">
                    {data.expenses.map(expense => (
                      <li key={expense.id}>
                        <Link to={`/expenses/${expense.id}`}>
                          <div className="section-heading">
                            <span className="expense-icon" aria-hidden="true">
                              ◈
                            </span>
                            <span className={`badge ${expense.settled ? 'settled' : ''}`}>
                              {expense.settled ? 'Saldado' : 'Por completar'}
                            </span>
                          </div>
                          <h3>{expense.title}</h3>
                          <p>
                            {people(expense.participants.length)} · Total{' '}
                            <Money amount={expense.total_minor} />
                          </p>
                          <div className="expense-bottom">
                            <span>Pendiente del grupo</span>
                            <Money amount={expense.outstanding_total_minor} />
                          </div>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>
          </>
        )
      )}
    </>
  );
}
