import { useCallback, useState } from 'react';
import { Link, NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { api } from './api/client';
import type { Account } from './api/types';
import { ActiveAccount, useActiveAccount } from './session/ActiveAccount';
import { useLoad } from './pages/useLoad';
import Dashboard from './pages/Dashboard';
import Transfer from './pages/Transfer';
import History from './pages/History';
import SharedExpenseDetail from './pages/SharedExpenseDetail';
import CreateSharedExpense from './pages/CreateSharedExpense';
import CreateAccount from './pages/CreateAccount';
import CreditPath from './pages/CreditPath';
import Login from './pages/Login';
import { Button } from './components/Button';
import { Spinner } from './components/Spinner';
import { ErrorBanner } from './components/ErrorBanner';

function Shell({ onCreated }: { onCreated: (account: Account) => void }) {
  const { active, signOut } = useActiveAccount();
  const location = useLocation();
  const navigate = useNavigate();
  function leave() {
    signOut();
    navigate('/entrar', { replace: true });
  }
  if (!active) {
    return (
      <main id="main" className="auth-shell">
        <Link to="/entrar" className="brand">
          <span className="brand-mark" aria-hidden="true">
            h
          </span>
          habi<span>capital</span>
        </Link>
        <Routes>
          <Route path="/entrar" element={<Login />} />
          <Route path="/cuentas/nueva" element={<CreateAccount onCreated={onCreated} />} />
          <Route path="*" element={<Navigate to="/entrar" replace />} />
        </Routes>
      </main>
    );
  }
  // La ruta al crédito es una habitación distinta: oscura y a sangre
  // completa. Las otras cinco pantallas no cambian.
  const dark = !!active && location.pathname === '/ruta';
  return (
    <div className={dark ? 'app app-dark' : 'app'}>
      <a className="skip-link" href="#main">
        Ir al contenido
      </a>
      <header className="app-header">
        <div className="header-inner">
          <Link to="/" className="brand">
            <span className="brand-mark" aria-hidden="true">
              h
            </span>
            habi<span>capital</span>
          </Link>
          <nav aria-label="Navegación principal">
            <NavLink end to="/">
              Inicio
            </NavLink>
            <NavLink to="/transfer">Transferir</NavLink>
            <NavLink to="/history">Historial</NavLink>
            <NavLink to="/ruta">Tu ruta</NavLink>
          </nav>
          <div className="session-account">
            <div>
              <strong>{active.display_name}</strong>
              <span>@{active.handle}</span>
            </div>
            <Button className="secondary" onClick={leave}>
              Cerrar sesión
            </Button>
          </div>
        </div>
      </header>
      <main
        id="main"
        className={dark ? 'shell shell-dark' : 'shell'}
        key={`${active?.id}:${location.pathname}:${location.search}`}
      >
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/cuentas/nueva" element={<CreateAccount onCreated={onCreated} />} />
          <Route path="/transfer" element={<Transfer />} />
          <Route path="/history" element={<History />} />
          <Route path="/ruta" element={<CreditPath />} />
          <Route path="/expenses/new" element={<CreateSharedExpense />} />
          <Route path="/expenses/:expenseId" element={<SharedExpenseDetail />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <footer className="app-footer">
        <span>habi capital</span>
        <span>El dinero cuenta historias.</span>
      </footer>
    </div>
  );
}
export default function App() {
  const [createdAccounts, setCreatedAccounts] = useState<Account[]>([]);
  const { data, loading, error, retry } = useLoad(useCallback(() => api.accounts(), []));
  function onCreated(account: Account) {
    setCreatedAccounts(accounts => [...accounts, account]);
  }
  if (loading)
    return (
      <main className="shell">
        <Spinner />
      </main>
    );
  if (error)
    return (
      <main className="shell">
        <h1>HabiCapital</h1>
        <ErrorBanner message={error} retry={retry} />
      </main>
    );
  return (
    <ActiveAccount accounts={[...(data || []), ...createdAccounts]}>
      <Shell onCreated={onCreated} />
    </ActiveAccount>
  );
}
