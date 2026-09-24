import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useActiveAccount } from '../session/ActiveAccount';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { Field } from '../components/Field';

export default function Login() {
  // App carga estas cuentas con api.accounts(); no hay endpoint de login.
  const { accounts, select } = useActiveAccount();
  const navigate = useNavigate();
  const [handle, setHandle] = useState('');
  const [unknown, setUnknown] = useState(false);

  function enter(id: string) {
    select(id);
    navigate('/', { replace: true });
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!event.currentTarget.reportValidity()) return;
    event.currentTarget.reset(); // Se ignora la contraseña: solo existe para representar el formulario de login del reto; required exige un valor no vacío. No se lee, compara, envía ni guarda.
    const account = accounts.find(account => account.handle === handle.trim());
    if (!account) {
      setUnknown(true);
      return;
    }
    enter(account.id);
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Entra a tu cuenta</h1>
        </div>
      </div>
      <div className="simulation-notice">
        <strong>La autenticación es simulada para este reto.</strong>
        <p>
          Solo comprobamos que tu usuario exista. Cualquier contraseña no vacía funciona: no se envía, no se
          guarda y no se compara. No uses una contraseña real.
        </p>
      </div>
      <Card>
        <form onSubmit={submit} className="stack" autoComplete="off">
          <Field label="Usuario">
            <input
              name="handle"
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              required
              value={handle}
              onChange={event => {
                setHandle(event.target.value);
                setUnknown(false);
              }}
            />
          </Field>
          <Field label="Contraseña">
            <input type="password" required autoComplete="off" />
          </Field>
          {unknown && (
            <div className="error-banner" role="alert">
              <div>
                Ese usuario no existe. <Link to="/cuentas/nueva">Crea tu cuenta</Link> para entrar.
              </div>
            </div>
          )}
          <Button type="submit">Entrar</Button>
          <p>
            ¿No tienes cuenta? <Link to="/cuentas/nueva">Créala</Link>
          </p>
        </form>
      </Card>
      <section className="stack" aria-labelledby="demo-accounts-heading">
        <h2 id="demo-accounts-heading">Cuentas de demostración</h2>
        <p>Entra con un clic para explorar la demo.</p>
        <div className="demo-accounts">
          {accounts.map(account => (
            <Button key={account.id} className="secondary" onClick={() => enter(account.id)}>
              <span>
                {account.display_name}
                <span className="demo-handle">@{account.handle}</span>
              </span>
            </Button>
          ))}
        </div>
        {accounts.length === 0 && <p>Aún no hay cuentas. Crea la primera para empezar.</p>}
      </section>
    </>
  );
}
