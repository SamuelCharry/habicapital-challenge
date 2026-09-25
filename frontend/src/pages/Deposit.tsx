import { useCallback, useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { useActiveAccount } from '../session/ActiveAccount';
import { useLoad } from './useLoad';
import { Card } from '../components/Card';
import { Money } from '../components/Money';
import { Button } from '../components/Button';
import { AmountField, pesosToMinor } from '../components/Field';
import { ErrorBanner } from '../components/ErrorBanner';
import { SuccessCard } from '../components/SuccessCard';
import { Spinner } from '../components/Spinner';

/** Montos de un toque: cubren las recargas habituales sin tener que teclear. */
const QUICK_AMOUNTS = ['50000', '100000', '200000', '500000'];

export default function Deposit() {
  const { active } = useActiveAccount();
  const id = active!.id;
  const [amount, setAmount] = useState('');
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState('');
  const [done, setDone] = useState<{ amount: bigint; balance: bigint } | null>(null);
  // El endpoint de depósitos no es idempotente: un doble clic serían dos
  // recargas. El ref bloquea el segundo envío antes de que React re-renderice.
  const sending = useRef(false);
  const { data, loading, error, retry } = useLoad(useCallback(() => api.balance(id), [id]));
  const minor = pesosToMinor(amount);

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    if (sending.current || !minor) return;
    sending.current = true;
    setPending(true);
    setFailure('');
    try {
      const response = await api.deposit(id, minor);
      setDone({ amount: minor, balance: response.balance_minor });
    } catch (error) {
      setFailure(error instanceof Error ? error.message : 'No pudimos confirmar la recarga.');
    } finally {
      sending.current = false;
      setPending(false);
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Recargar cuenta</h1>
        </div>
      </div>
      {loading ? (
        <Spinner />
      ) : error ? (
        <ErrorBanner message={error} retry={retry} />
      ) : done ? (
        <SuccessCard title="Recarga confirmada">
          <p>
            Agregaste <Money amount={done.amount} />. Tu saldo ahora es <Money amount={done.balance} />.
          </p>
          <div className="actions">
            <Link className="button" to="/">
              Volver al inicio
            </Link>
            <Button
              className="secondary"
              onClick={() => {
                setDone(null);
                setAmount('');
              }}
            >
              Hacer otra recarga
            </Button>
          </div>
        </SuccessCard>
      ) : (
        data && (
          <div className="form-grid">
            <Card>
              <form onSubmit={submit} className="stack">
                <h2>¿Cuánto quieres agregar?</h2>
                <fieldset disabled={pending} className="stack">
                  <div className="quick-amounts" role="group" aria-label="Montos sugeridos">
                    {QUICK_AMOUNTS.map(value => (
                      <button
                        type="button"
                        key={value}
                        className={amount === value ? 'selected' : ''}
                        aria-pressed={amount === value}
                        onClick={() => {
                          setAmount(value);
                          setFailure('');
                        }}
                      >
                        <Money amount={BigInt(value) * 100n} />
                      </button>
                    ))}
                  </div>
                  <AmountField
                    value={amount}
                    onChange={value => {
                      setAmount(value);
                      setFailure('');
                    }}
                  />
                </fieldset>
                {failure && <ErrorBanner message={failure} />}
                <Button type="submit" disabled={pending || !minor}>
                  {pending ? 'Confirmando recarga…' : 'Confirmar recarga'} <span aria-hidden="true">+</span>
                </Button>
              </form>
            </Card>
            <aside className="stack">
              <Card>
                <h2 className="eyebrow">Saldo actual</h2>
                <p className="aside-figure">
                  <Money amount={data.balance_minor} />
                </p>
                {minor && (
                  <p className="muted">
                    Después de recargar: <Money amount={data.balance_minor + minor} />
                  </p>
                )}
              </Card>
            </aside>
          </div>
        )
      )}
    </>
  );
}
