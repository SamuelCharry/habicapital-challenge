import type { ReactNode } from 'react';
export function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="empty">
      <span className="empty-mark" aria-hidden="true">
        ↗
      </span>
      <h3>{title}</h3>
      <div>{children}</div>
    </div>
  );
}
