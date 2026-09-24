import type { Account } from '../api/types';
export function AccountSwitcher({
  accounts,
  value,
  onChange,
}: {
  accounts: Account[];
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <label className="account-switcher">
      <span>Cuenta activa</span>
      <select value={value} onChange={e => onChange(e.target.value)} disabled={!accounts.length}>
        {!accounts.length && <option value="">Sin cuentas disponibles</option>}
        {accounts.map(account => (
          <option value={account.id} key={account.id}>
            {account.display_name} · @{account.handle}
          </option>
        ))}
      </select>
    </label>
  );
}
