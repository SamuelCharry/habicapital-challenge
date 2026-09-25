import { useEffect, useRef, type ReactNode } from 'react';
import { Card } from './Card';

/** El reemplazo del formulario por la confirmación no se anunciaba: quien usa
 *  lector de pantalla movía dinero y después recibía silencio, porque el botón
 *  que tenía el foco desaparecía del DOM. role="status" lo anuncia y el foco
 *  pasa al título, que es donde sigue la lectura. */
export function SuccessCard({ title, children }: { title: string; children: ReactNode }) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus();
  }, []);
  return (
    <Card className="success-card" role="status">
      <span className="success-mark" aria-hidden="true">
        ✓
      </span>
      <h2 ref={heading} tabIndex={-1}>
        {title}
      </h2>
      {children}
    </Card>
  );
}
