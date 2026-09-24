import { Button } from './Button';
export function ErrorBanner({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div className="error-banner" role="alert">
      <div>
        <strong>No pudimos completar la solicitud</strong>
        <p>{message}</p>
      </div>
      {retry && (
        <Button className="secondary" onClick={retry}>
          Reintentar
        </Button>
      )}
    </div>
  );
}
