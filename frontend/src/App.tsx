import { useCallback } from 'react';
import { Link, NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { api } from './api/client';
import { ActiveAccount, useActiveAccount } from './session/ActiveAccount';
import { useLoad } from './pages/useLoad';
import Dashboard from './pages/Dashboard';
import Transfer from './pages/Transfer';
import History from './pages/History';
import SharedExpenseDetail from './pages/SharedExpenseDetail';
import CreateSharedExpense from './pages/CreateSharedExpense';
import CreditPath from './pages/CreditPath';
import { AccountSwitcher } from './components/AccountSwitcher';
import { EmptyState } from './components/EmptyState';
import { Spinner } from './components/Spinner';
import { ErrorBanner } from './components/ErrorBanner';
import { Button } from './components/Button';

function Shell({ refresh }: { refresh: () => void }) {
  const { accounts, active, select } = useActiveAccount();
  const location = useLocation();
  // La ruta al crédito es una habitación distinta: oscura y a sangre
  // completa. Las otras cinco pantallas no cambian.
  const dark = location.pathname === '/ruta';
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
          <AccountSwitcher accounts={accounts} value={active?.id || ''} onChange={select} />
        </div>
      </header>
      <main id="main" className={location.pathname === '/ruta' ? 'shell shell-dark' : 'shell'} key={`${active?.id}:${location.pathname}:${location.search}`}>
        {!active ? (
          <EmptyState title="Todo empieza con una cuenta">
            <p>
              Aún no hay cuentas disponibles. Crea las cuentas de demostración en la API y actualiza para
              empezar.
            </p>
            <Button onClick={refresh}>Actualizar cuentas</Button>
          </EmptyState>
        ) : (
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/transfer" element={<Transfer />} />
            <Route path="/history" element={<History />} />
            <Route path="/ruta" element={<CreditPath />} />
            <Route path="/expenses/new" element={<CreateSharedExpense />} />
            <Route path="/expenses/:expenseId" element={<SharedExpenseDetail />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        )}
      </main>
      <footer className="app-footer">
        <span>habi capital</span>
        <span>El dinero cuenta historias.</span>
      </footer>
    </div>
  );
}
export default function App() {
  const { data, loading, error, retry } = useLoad(useCallback(() => api.accounts(), []));
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
    <ActiveAccount accounts={data || []}>
      <Shell refresh={retry} />
    </ActiveAccount>
  );
}
