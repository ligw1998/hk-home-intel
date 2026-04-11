"use client";

import { useEffect, useState } from "react";

type HealthResponse = {
  status: string;
  environment: string;
  app_name: string;
  app_version: string;
  api_prefix: string;
  database: {
    healthy: boolean;
    dialect: string;
    url_redacted: string;
  };
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export default function HomePage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadHealth() {
      try {
        const response = await fetch(`${API_BASE}/api/v1/health`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const payload = (await response.json()) as HealthResponse;
        if (!cancelled) {
          setHealth(payload);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unknown error");
        }
      }
    }

    loadHealth();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="page-shell">
      <section className="hero-card">
        <p className="eyebrow">Phase 0</p>
        <h1>HK Home Intel</h1>
        <p className="lead">
          Local-first Hong Kong residential property research workspace. This
          baseline only wires the app shell, runtime config, health endpoint,
          worker placeholder, and local development workflow.
        </p>
      </section>

      <section className="grid">
        <article className="panel">
          <h2>System Status</h2>
          {health ? (
            <dl className="kv-list">
              <div>
                <dt>API</dt>
                <dd>{health.status}</dd>
              </div>
              <div>
                <dt>Environment</dt>
                <dd>{health.environment}</dd>
              </div>
              <div>
                <dt>Version</dt>
                <dd>{health.app_version}</dd>
              </div>
              <div>
                <dt>Database</dt>
                <dd>
                  {health.database.dialect} /{" "}
                  {health.database.healthy ? "healthy" : "unhealthy"}
                </dd>
              </div>
            </dl>
          ) : (
            <p className="muted">
              {error
                ? `API unavailable: ${error}`
                : "Waiting for API health response..."}
            </p>
          )}
        </article>

        <article className="panel">
          <h2>Phase 0 Scope</h2>
          <ul className="bullet-list">
            <li>Monorepo directory scaffold</li>
            <li>FastAPI application shell and health route</li>
            <li>Worker command placeholder</li>
            <li>Local environment config and runtime directories</li>
            <li>Next.js dashboard shell for future tabs</li>
          </ul>
        </article>

        <article className="panel">
          <h2>Next Milestones</h2>
          <ul className="bullet-list">
            <li>Schema migrations and domain tables</li>
            <li>First official source adapter</li>
            <li>Map page and development index endpoint</li>
            <li>Watchlist CRUD and persistence</li>
          </ul>
        </article>
      </section>
    </main>
  );
}
