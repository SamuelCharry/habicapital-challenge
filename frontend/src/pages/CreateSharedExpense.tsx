import { useCallback, useRef, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useActiveAccount } from '../session/ActiveAccount';
import { useLoad } from './useLoad';
import { Card } from '../components/Card';
import { Avatar } from '../components/Avatar';
import { Money } from '../components/Money';
import { Button } from '../components/Button';
import { Field, AmountField, pesosToMinor } from '../components/Field';
import { EmptyState } from '../components/EmptyState';
import { ErrorBanner } from '../components/ErrorBanner';
import { Spinner } from '../components/Spinner';
import { people } from '../utils/money';

// Mirrors EqualSplitStrategy: ascending canonical UUIDs receive the remainder.
export function equalPreview(total: bigint, ids: string[]): Map<string, bigint> {
  if (!ids.length || total < BigInt(ids.length)) return new Map();
  const count = BigInt(ids.length);
  return new Map(
    [...ids].sort().map((id, index) => [id, total / count + (BigInt(index) < total % count ? 1n : 0n)]),
  );
}

export default function CreateSharedExpense() {
  const { active } = useActiveAccount();
  const navigate = useNavigate();
  const [title, setTitle] = useState('');
  const [amount, setAmount] = useState('');
  const [ids, setIds] = useState<string[]>([active!.id]);
  const [payer, setPayer] = useState(active!.id);
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState('');
  const sending = useRef(false);
  const { data, loading, error, retry } = useLoad(useCallback(() => api.accounts(), []));
  const selected = (data || []).filter(account => ids.includes(account.id));
  const minor = pesosToMinor(amount);
  const shares = equalPreview(
    minor || 0n,
    selected.map(account => account.id),
  );
  function toggle(id: string) {
    setIds(current => (current.includes(id) ? current.filter(value => value !== id) : [...current, id]));
    if (id === payer && ids.includes(id)) setPayer('');
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (sending.current || !minor || !title.trim() || !shares.size || !shares.has(payer)) return;
    sending.current = true;
    setPending(true);
    setFailure('');
    try {
      const expense = await api.createExpense({
        title: title.trim(),
        total_minor: minor,
        currency: 'COP',
        payer_account_id: payer,
        participant_account_ids: selected.map(a => a.id),
        split: 'equal',
      });
      navigate(`/expenses/${expense.id}`);
    } catch (error) {
      setFailure(error instanceof Error ? error.message : 'No pudimos crear el gasto.');
    } finally {
      sending.current = false;
      setPending(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">UN PLAN EN COMÚN</p>
          <h1>Crear gasto compartido</h1>
          <p>Una sola cuenta, una parte justa para cada persona.</p>
        </div>
      </div>
      {loading ? (
        <Spinner />
      ) : error ? (
        <ErrorBanner message={error} retry={retry} />
      ) : !data?.length ? (
        <Card>
          <EmptyState title="Primero necesitas una cuenta">
            <p>Las cuentas disponibles aparecerán aquí para que puedas invitar a tu grupo.</p>
            <Button onClick={retry}>Actualizar cuentas</Button>
          </EmptyState>
        </Card>
      ) : (
        <form onSubmit={submit} className="form-grid">
          <Card>
            <fieldset className="stack" disabled={pending}>
              <h2>Los detalles del plan</h2>
              <Field label="Nombre del gasto">
                <input
                  required
                  maxLength={200}
                  placeholder="Ej. Cena del viernes"
                  value={title}
                  onChange={e => setTitle(e.target.value)}
                />
              </Field>
              <AmountField label="Total en pesos" value={amount} onChange={setAmount} />
              <fieldset className="participants-picker">
                <legend>¿Quiénes participan?</legend>
                {data.map(account => (
                  <label className="participant-option" key={account.id}>
                    <input
                      type="checkbox"
                      checked={ids.includes(account.id)}
                      onChange={() => toggle(account.id)}
                    />
                    <Avatar name={account.display_name} />
                    <span>
                      <strong>{account.display_name}</strong>
                      <small>@{account.handle}</small>
                    </span>
                  </label>
                ))}
              </fieldset>
              <Field
                label="¿Quién pagó la cuenta?"
                hint="Su parte se registra como cubierta. Las demás personas le pagan a esta cuenta."
              >
                <select value={payer} onChange={e => setPayer(e.target.value)} required>
                  <option value="" disabled>
                    Selecciona a quien pagó
                  </option>
                  {selected.map(account => (
                    <option key={account.id} value={account.id}>
                      {account.display_name} · @{account.handle}
                    </option>
                  ))}
                </select>
              </Field>
            </fieldset>
          </Card>
          <aside className="stack">
            <Card className="preview-card">
              <p className="eyebrow">ANTES DE CREAR</p>
              <h2>Así se divide</h2>
              <p>Reparto en partes iguales · {people(selected.length)}</p>
              {!shares.size ? (
                <EmptyState title="Arma tu grupo">
                  <p>
                    Escribe el total y selecciona participantes para ver cuánto corresponde a cada persona.
                  </p>
                </EmptyState>
              ) : (
                <>
                  <ul className="preview-list">
                    {selected.map(account => (
                      <li key={account.id}>
                        <div>
                          <strong>{account.display_name}</strong>
                          <small>{payer === account.id ? 'Quien pagó · parte cubierta' : 'Por pagar'}</small>
                        </div>
                        <Money amount={shares.get(account.id)!} />
                      </li>
                    ))}
                  </ul>
                  <div className="summary-line">
                    <strong>Total</strong>
                    <Money amount={minor!} />
                  </div>
                  <p className="muted">
                    Si quedan centavos, se asignan uno a uno según el orden de las cuentas. El total siempre
                    coincide.
                  </p>
                </>
              )}
              {failure && <ErrorBanner message={failure} />}
              <Button type="submit" disabled={pending || !title.trim() || !shares.size || !shares.has(payer)}>
                {pending ? 'Creando gasto…' : failure ? 'Reintentar creación' : 'Crear gasto compartido'}
              </Button>
            </Card>
            <p className="form-note">
              Crear el gasto organiza las cuentas. El dinero se mueve cuando cada persona confirma su
              transferencia.
            </p>
          </aside>
        </form>
      )}
    </>
  );
}
