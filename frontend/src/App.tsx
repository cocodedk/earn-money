import { useEffect, useState } from "react";

type HealthResponse = {
  status: string;
  db: boolean;
};

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/health/")
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        return (await response.json()) as HealthResponse;
      })
      .then(setHealth)
      .catch((err) => setError(String(err)));
  }, []);

  return (
    <main style={{ fontFamily: "ui-monospace, monospace", padding: "2rem" }}>
      <h1>Cookbook scanner</h1>
      <p>Platform skeleton — no scanner stub wired yet.</p>
      <section>
        <h2>Backend health</h2>
        {health && (
          <pre>{JSON.stringify(health, null, 2)}</pre>
        )}
        {error && (
          <p style={{ color: "crimson" }}>
            <strong>health probe failed:</strong> {error}
          </p>
        )}
        {!health && !error && <p>Checking…</p>}
      </section>
    </main>
  );
}
