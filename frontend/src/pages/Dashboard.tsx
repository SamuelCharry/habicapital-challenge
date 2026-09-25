import { useCallback } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { useActiveAccount } from '../session/ActiveAccount';
import { useLoad } from './useLoad';
import { Card } from '../components/Card';
import { HeroParticles } from '../components/HeroParticles';
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
        <HeroParticles />
        <div>
          <h1>Hola, {active!.display_name.split(' ')[0]}.</h1>
          <p>Las cuentas claras. Los planes, compartidos.</p>
        </div>
        <div className="hero-balance">
          <span>Saldo disponible · @{active!.handle}</span>
          {data ? (
            <Money className="balance" amount={data.balance.balance_minor} />
          ) : (
            <span className="balance-placeholder" aria-hidden="true" />
          )}
          <div className="hero-actions">
            <Link className="button ghost" to="/recargar">
              Recargar
            </Link>
            <Link className="button light" to="/transfer">
              Transferir dinero
            </Link>
          </div>
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
            <div className="dashboard-grid">
              <Card>
                <div className="section-heading">
                  <h2>Actividad reciente</h2>
                  <Link to="/history">Ver todo <span aria-hidden="true">→</span></Link>
                </div>
                <div className="scroll-area" tabIndex={0} role="region" aria-label="Actividad reciente">
                  <MovementList movements={data.history} />
                </div>
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
                    <Link to="/expenses/new">Crear un gasto <span aria-hidden="true">→</span></Link>
                  </EmptyState>
                ) : (
                  <div className="scroll-area" tabIndex={0} role="region" aria-label="Gastos compartidos">
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
                  </div>
                )}
              </Card>
            </div>
          </>
        )
      )}
    </>
  );
}
