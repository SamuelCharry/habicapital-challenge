import { useId, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { Account } from '../api/types';
import { useActiveAccount } from '../session/ActiveAccount';
import { Avatar } from '../components/Avatar';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { ErrorBanner } from '../components/ErrorBanner';
import { Field } from '../components/Field';

export default function CreateAccount({ onCreated }: { onCreated: (account: Account) => void }) {
  const { active, select } = useActiveAccount();
  const navigate = useNavigate();
  const hintId = useId();
  const [displayName, setDisplayName] = useState('');
  const [handle, setHandle] = useState('');
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState('');
  const sending = useRef(false);
  const validHandle = /^[a-z0-9_]{3,20}$/.test(handle);
  const invalidHandle = handle !== '' && !validHandle;
  const validName = displayName.trim().length > 0 && displayName.length <= 200;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (sending.current || !validHandle || !validName) return;
    sending.current = true;
    setPending(true);
    setFailure('');
    try {
      const account = await api.createAccount(handle, displayName);
      onCreated(account);
      select(account.id);
      navigate('/', { replace: true });
    } catch (error) {
      setFailure(error instanceof Error ? error.message : 'No pudimos crear la cuenta. Vuelve a intentar.');
    } finally {
      sending.current = false;
      setPending(false);
    }
  }

  return (
    <>
      {!active && <Link to="/entrar">← Volver a entrar</Link>}
      <div className="page-heading">
        <div>
          <h1>{active ? 'Crear una cuenta' : 'Todo empieza con una cuenta'}</h1>
          <p>Elige tu nombre y tu usuario para empezar.</p>
        </div>
      </div>
      <Card className="create-account-card">
        <form onSubmit={submit} className="stack" aria-busy={pending}>
          <div className="create-account-preview">
            <Avatar name={displayName || 'Tu cuenta'} />
            <div>
              <h2>{displayName || 'Tu nueva cuenta'}</h2>
              <p className="muted">{handle ? `@${handle}` : 'El dinero cuenta historias.'}</p>
            </div>
          </div>
          <fieldset disabled={pending} className="stack">
            <Field label="Nombre para mostrar" hint="Así te verán las otras personas. Máximo 200 caracteres.">
              <input
                name="display_name"
                autoComplete="name"
                required
                maxLength={200}
                value={displayName}
                onChange={event => setDisplayName(event.target.value)}
              />
            </Field>
            <Field label="Usuario">
              <input
                name="handle"
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                required
                pattern="^[a-z0-9_]{3,20}$"
                value={handle}
                onChange={event => setHandle(event.target.value)}
                aria-invalid={invalidHandle}
                aria-describedby={hintId}
              />
              <small id={hintId} className={invalidHandle ? 'invalid' : ''} aria-live="polite">
                3 a 20 caracteres: minúsculas, números y guion bajo. Sin espacios, tampoco al inicio ni al
                final.
                {invalidHandle && ' El usuario no cumple esta regla.'}
              </small>
            </Field>
          </fieldset>
          {failure && <ErrorBanner message={failure} />}
          <Button type="submit" disabled={pending || !validHandle || !validName}>
            {pending ? 'Creando cuenta…' : 'Crear cuenta'}
          </Button>
        </form>
      </Card>
    </>
  );
}
