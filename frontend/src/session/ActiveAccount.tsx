import { createContext, useContext, useState, type ReactNode } from 'react';
import type { Account } from '../api/types';
interface Session {
  accounts: Account[];
  active: Account | null;
  select: (id: string) => void;
}
const Context = createContext<Session | null>(null);
export function ActiveAccount({ accounts, children }: { accounts: Account[]; children: ReactNode }) {
  const [selected, setSelected] = useState(() => {
    try {
      return localStorage.getItem('habicapital.active-account') || '';
    } catch {
      return '';
    }
  });
  const active = accounts.find(account => account.id === selected) || accounts[0] || null;
  function select(id: string) {
    setSelected(id);
    try {
      localStorage.setItem('habicapital.active-account', id);
    } catch {
      /* Storage is optional. */
    }
  }
  return <Context.Provider value={{ accounts, active, select }}>{children}</Context.Provider>;
}
export function useActiveAccount() {
  const context = useContext(Context);
  if (!context) throw new Error('Falta el contexto de cuenta activa.');
  return context;
}
