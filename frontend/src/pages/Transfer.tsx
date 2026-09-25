import { useCallback, useRef, useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, encodeRequest } from '../api/client';
import type { TransferResult } from '../api/types';
import { useActiveAccount } from '../session/ActiveAccount';
import { useLoad } from './useLoad';
import { Card } from '../components/Card';
import { Money } from '../components/Money';
import { Button } from '../components/Button';
import { Field, AmountField, pesosToMinor } from '../components/Field';
import { EmptyState } from '../components/EmptyState';
import { ErrorBanner } from '../components/ErrorBanner';
import { SuccessCard } from '../components/SuccessCard';
import { Spinner } from '../components/Spinner';

export default function Transfer() {
  const { active } = useActiveAccount();
  const id = active!.id;
  const [params] = useSearchParams();
  const [destination, setDestination] = useState('');
  const [expenseId, setExpenseId] = useState(params.get('expense') || '');
  const [amount, setAmount] = useState('');
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState('');
  const [result, setResult] = useState<TransferResult | null>(null);
  const attempt = useRef<{ fingerprint: string; key: string } | null>(null);
  const sending = useRef(false);
  const load = useCallback(async () => {
    const [accounts, balance, expenses] = await Promise.all([
      api.accounts(),
      api.balance(id),
      api.expenses(id),
    ]);
    return { accounts, balance, expenses };
  }, [id]);
  const { data, loading, error, retry } = useLoad(load);
  const expenses = data?.expenses.filter(item => item.payer !== id) || [];
  const expense = expenses.find(item => item.id === expenseId);
  const recipient = expense?.payer || destination;
  const minor = pesosToMinor(amount);

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    if (sending.current || !minor || !recipient || recipient === id || (expenseId && !expense)) return;
    const body = {
      source_account_id: id,
      destination_account_id: recipient,
      amount_minor: minor,
      currency: 'COP' as const,
      shared_expense_id: expense?.id || null,
    };
    const fingerprint = encodeRequest(body);
    if (attempt.current?.fingerprint !== fingerprint)
      attempt.current = { fingerprint, key: crypto.randomUUID() };
    sending.current = true;
    setPending(true);
    setFailure('');
    try {
      const response = await api.transfer({ ...body, idempotency_key: attempt.current.key });
      setResult(response);
      attempt.current = null;
    } catch (error) {
      setFailure(error instanceof Error ? error.message : 'No pudimos confirmar la transferencia.');
    } finally {
      sending.current = false;
      setPending(false);
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Transferir dinero</h1>
        </div>
      </div>
      {loading ? (
        <Spinner />
      ) : error ? (
        <ErrorBanner message={error} retry={retry} />
      ) : (
        data &&
        (result ? (
          <SuccessCard title="Transferencia confirmada">
            <p>
              Tu pago de <Money amount={minor!} /> fue recibido.
            </p>
            {result.shared_expense_id && (
              <Link className="context-chip" to={`/expenses/${result.shared_expense_id}`}>
                <span aria-hidden="true">◈</span> {expense?.title} <span aria-hidden="true">→</span>
              </Link>
            )}
            <div className="actions">
              <Link className="button" to="/history">
                Ver en el historial
              </Link>
              <Link className="button secondary" to="/">
                Volver al inicio
              </Link>
            </div>
          </SuccessCard>
        ) : data.accounts.filter(a => a.id !== id).length === 0 ? (
          <Card>
            <EmptyState title="Hace falta alguien al otro lado">
              <p>
                Aún no hay otra cuenta a la que puedas transferir. Cuando esté disponible, aparecerá aquí.
              </p>
              <Button onClick={retry}>Actualizar cuentas</Button>
            </EmptyState>
          </Card>
        ) : (
          <div className="form-grid">
            <Card>
              <form onSubmit={submit} className="stack">
                <h2>¿A quién le envías?</h2>
                <fieldset disabled={pending} className="stack">
                  <Field label="Gasto compartido (opcional)">
                    <select
                      value={expenseId}
                      onChange={e => {
                        setExpenseId(e.target.value);
                        setFailure('');
                      }}
                    >
                      <option value="">Sin gasto asociado</option>
                      {expenses.map(item => (
                        <option value={item.id} key={item.id}>
                          {item.title}
                          {item.settled ? ' · Saldado' : ''}
                        </option>
                      ))}
                    </select>
                  </Field>
                  {!expenses.length && (
                    <p className="muted">
                      Aún no tienes gastos para pagar. Puedes enviar dinero sin asociarlo a uno.
                    </p>
                  )}
                  {expenseId && !expense && (
                    <ErrorBanner message="Este gasto no está disponible para pagar desde tu cuenta. Elige otro o envía sin gasto asociado." />
                  )}
                  <Field
                    label="Cuenta de destino"
                    hint={expense ? 'Este pago se enviará a quien pagó el gasto.' : undefined}
                  >
                    <select
                      required
                      value={recipient}
                      disabled={!!expense}
                      onChange={e => {
                        setDestination(e.target.value);
                        setFailure('');
                      }}
                    >
                      <option value="" disabled>
                        Selecciona una persona
                      </option>
                      {data.accounts
                        .filter(a => a.id !== id)
                        .map(account => (
                          <option value={account.id} key={account.id}>
                            {account.display_name} · @{account.handle}
                          </option>
                        ))}
                    </select>
                  </Field>
                  <AmountField
                    value={amount}
                    onChange={value => {
                      setAmount(value);
                      setFailure('');
                    }}
                  />
                </fieldset>
                {failure && (
                  <ErrorBanner
                    message={failure}
                    retry={() => {
                      void submit();
                    }}
                  />
                )}
                <Button type="submit" disabled={pending || !minor || !recipient || (!!expenseId && !expense)}>
                  {pending
                    ? 'Confirmando transferencia…'
                    : failure
                      ? 'Reintentar transferencia'
                      : 'Confirmar transferencia'}{' '}
                  <span aria-hidden="true">↗</span>
                </Button>
              </form>
            </Card>
            <aside className="stack">
              <Card>
                <p className="eyebrow">DESDE TU CUENTA</p>
                <h2>{active!.display_name}</h2>
                <p className="muted">@{active!.handle}</p>
                <div className="summary-line">
                  <span>Saldo disponible</span>
                  <Money amount={data.balance.balance_minor} />
                </div>
              </Card>
              <Card className={expense ? 'context-card' : ''}>
                <h2>{expense ? 'Un pago con contexto' : 'Una transferencia directa'}</h2>
                {expense ? (
                  <>
                    <Link className="context-chip" to={`/expenses/${expense.id}`}>
                      <span aria-hidden="true">◈</span> {expense.title}
                    </Link>
                    <p>Este pago quedará en el historial del gasto y reducirá tu parte pendiente.</p>
                    <div className="summary-line">
                      <span>Tu pendiente</span>
                      <Money
                        amount={expense.participants.find(p => p.account_id === id)!.outstanding_minor}
                      />
                    </div>
                  </>
                ) : (
                  <p>
                    El dinero llegará a la cuenta de destino. En tu historial aparecerá como «Sin gasto
                    asociado».
                  </p>
                )}
              </Card>
            </aside>
          </div>
        ))
      )}
    </>
  );
}
