import { useEffect, useState } from "react";
import { getHealth, type HealthResponse } from "./api/client";

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    getHealth()
      .then((result) => {
        if (active) setHealth(result);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <main className="shell">
      <header className="brand">HabiCapital<span> / Foundation</span></header>
      <section className="status-card" aria-labelledby="status-title">
        <p className="eyebrow">System status</p>
        <h1 id="status-title">A connected beginning.</h1>
        <p className="intro">The foundation for what comes next.</p>
        <div className="status" role="status" aria-live="polite">
          <span className={`indicator ${health?.status === "ok" ? "healthy" : ""}`} aria-hidden="true" />
          <p>
            {failed
              ? "Unable to reach the backend. Please try again later."
              : health
                ? health.status === "ok"
                  ? "Backend online"
                  : "Backend degraded"
                : "Checking connection…"}
          </p>
        </div>
        {health && (
          <dl className="details">
            <div><dt>Database</dt><dd>{health.database === "ok" ? "Connected" : "Unavailable"}</dd></div>
            <div><dt>Version</dt><dd>{health.version}</dd></div>
          </dl>
        )}
      </section>
    </main>
  );
}
