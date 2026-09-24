import { useCallback, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { CreditPath as CreditPathData } from '../api/types';
import { CreditMap } from '../components/CreditMap';
import { ErrorBanner } from '../components/ErrorBanner';
import { useActiveAccount } from '../session/ActiveAccount';
import { formatMoney } from '../utils/money';
import { useLoad } from './useLoad';

type Row = { label: string; value: string; source: string; moved: boolean };

function rows(path: CreditPathData, waypointIndex: number): Row[] {
  const { profile, trajectory } = path;
  const current = trajectory[waypointIndex];
  const moved = Boolean(current) && waypointIndex > 0;
  const savings = current ? current.monthly_savings_minor : profile.monthly_savings_minor;
  const months = current ? current.months_consistent : profile.months_consistent;
  const compliance =
    profile.compliance_ratio === null
      ? '—'
      : `${Math.round(profile.compliance_ratio * 100)}%`;

  return [
    {
      label: 'Ahorro mensual constante',
      value: formatMoney(savings),
      source:
        profile.months_consistent === 1
          ? 'de tu depósito del último mes'
          : `de tus depósitos de los últimos ${profile.months_consistent} meses`,
      moved,
    },
    {
      label: 'Meses de constancia',
      value: String(months),
      source: 'de tu historial',
      moved,
    },
    {
      label: 'Cumplimiento compartido',
      value: compliance,
      source:
        profile.compliance_ratio === null
          ? 'aún sin gastos compartidos'
          : 'de lo que debías en gastos compartidos',
      moved: false,
    },
    {
      label: 'Cuota inicial acumulada',
      value: formatMoney(profile.down_payment_minor),
      source: 'de tu saldo',
      moved: false,
    },
  ];
}

export default function CreditPath() {
  const { active } = useActiveAccount();
  const accountId = active?.id;
  const { data, loading, error, retry } = useLoad(
    useCallback(() => (accountId ? api.creditPath(accountId) : Promise.resolve(null)), [accountId]),
  );
  const [position, setPosition] = useState(0);

  if (error) return <ErrorBanner message={error} retry={retry} />;

  const waypointIndex = data?.trajectory.length
    ? Math.round((position / 100) * (data.trajectory.length - 1))
    : 0;

  return (
    <div className="credit-page">
      <p className="eyebrow">TU POSICIÓN HOY</p>
      <h1>{loading || !data ? 'Calculando tu posición…' : data.headline}</h1>

      {data && (
        <>
          <dl className="credit-rows">
            {rows(data, waypointIndex).map(row => (
              <div key={row.label}>
                <dt>{row.label}</dt>
                <dd className={row.moved ? 'moved' : undefined}>{row.value}</dd>
                <span>{row.source}</span>
              </div>
            ))}
          </dl>

          <CreditMap path={data} position={position} />

          {data.trajectory.length > 0 && (
            <div className="credit-slider">
              <input
                type="range"
                min={0}
                max={100}
                step={1}
                value={position}
                onChange={event => setPosition(Number(event.target.value))}
                aria-label="Recorre la ruta desde hoy hasta el escenario en que calificas"
              />
              <div>
                <span>Hoy</span>
                <span>Calificas</span>
              </div>
            </div>
          )}

          {data.has_enough_evidence ? (
            <section className="credit-steps">
              <p className="eyebrow">TU RUTA</p>
              <ol>
                {data.steps.map(step => (
                  <li key={step.order}>
                    <span>{step.order}</span>
                    <span>{step.action}</span>
                    <span>{step.magnitude}</span>
                  </li>
                ))}
              </ol>
            </section>
          ) : (
            <section className="credit-empty">
              <span aria-hidden="true">◌</span>
              <p>Necesitamos al menos tres meses de actividad para situarte en el mapa.</p>
              <p className="credit-empty-detail">
                Llevas {data.profile.months_consistent}
                {data.profile.months_consistent === 1 ? ' mes' : ' meses'}.
              </p>
              <Link to="/">Volver al inicio →</Link>
            </section>
          )}

          <p className="credit-disclaimer">
            <strong>Esto no aprueba ni niega créditos.</strong> Muestra escenarios posibles a partir
            de tu comportamiento, calculados sobre un conjunto de datos público de crédito.
          </p>
        </>
      )}
    </div>
  );
}
