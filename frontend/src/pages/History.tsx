import { useCallback } from 'react';
import { api } from '../api/client';
import { useActiveAccount } from '../session/ActiveAccount';
import { useLoad } from './useLoad';
import { Card } from '../components/Card';
import { MovementList } from '../components/MovementList';
import { Spinner } from '../components/Spinner';
import { ErrorBanner } from '../components/ErrorBanner';
export default function History() {
  const { active } = useActiveAccount();
  const id = active!.id;
  const { data, loading, error, retry } = useLoad(useCallback(() => api.history(id), [id]));
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Tu historial</h1>
          <p>Todo lo que entra, lo que sale y la historia que lo acompaña.</p>
        </div>
      </div>
      <Card>
        <div className="section-heading">
          <h2>Movimientos de @{active!.handle}</h2>
          <span className="context-chip">◈ Con gasto asociado</span>
        </div>
        {loading ? (
          <Spinner />
        ) : error ? (
          <ErrorBanner message={error} retry={retry} />
        ) : (
          data && <MovementList movements={data} />
        )}
      </Card>
    </>
  );
}
