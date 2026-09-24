import { useId, type ReactNode } from 'react';
export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
export function pesosToMinor(value: string): bigint | null {
  if (!/^\d{1,17}$/.test(value)) return null;
  const amount = BigInt(`${value}00`);
  return amount > 0n && amount <= 9223372036854775807n ? amount : null;
}
export function AmountField({
  value,
  onChange,
  label = 'Monto en pesos',
  disabled = false,
}: {
  value: string;
  onChange: (value: string) => void;
  label?: string;
  disabled?: boolean;
}) {
  const hintId = useId();
  const invalid = value !== '' && pesosToMinor(value) === null;
  return (
    <label className="field">
      <span>{label}</span>
      <span className="amount-input">
        <span aria-hidden="true">$</span>
        <input
          value={value}
          onChange={e => onChange(e.target.value)}
          inputMode="numeric"
          pattern="[0-9]+"
          maxLength={17}
          required
          disabled={disabled}
          placeholder="0"
          aria-invalid={invalid}
          aria-describedby={hintId}
        />
        <span>COP</span>
      </span>
      <small id={hintId} className={invalid ? 'invalid' : ''}>
        {invalid
          ? 'Escribe un monto positivo válido, solo con dígitos.'
          : 'Pesos enteros, sin puntos ni comas. Ejemplo: 180000.'}
      </small>
    </label>
  );
}
