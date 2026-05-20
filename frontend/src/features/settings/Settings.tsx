import { PageHeader } from "../../components/PageHeader";
import { MetaList, MetaRow } from "../../components/MetaList";
import { Callout } from "../../components/Callout";
import { useSystemHealth } from "../../lib/useConnectionStatus";

const FRONTEND_VERSION =
  (import.meta.env.VITE_FRONTEND_VERSION as string | undefined) ?? "dev";

function BoolBadge({
  ok,
  testId,
}: {
  ok: boolean | undefined;
  testId: string;
}) {
  if (ok === undefined) {
    return (
      <span data-testid={testId} style={{ color: "var(--ink-muted)" }}>
        —
      </span>
    );
  }
  return (
    <span
      data-testid={testId}
      style={{ color: ok ? "var(--ok)" : "var(--err)" }}
    >
      {ok ? "up" : "down"}
    </span>
  );
}

function StatusBadge({ value }: { value: string | undefined }) {
  const ok = value === "ok";
  return (
    <span
      data-testid="settings-backend-status"
      style={{ color: ok ? "var(--ok)" : "var(--warn)" }}
    >
      {value ?? "—"}
    </span>
  );
}

export function Settings() {
  const query = useSystemHealth();
  return (
    <>
      <PageHeader title="Settings" />
      {query.isError ? (
        <Callout variant="error">
          Backend unreachable — system status cannot be loaded.
        </Callout>
      ) : null}
      <MetaList>
        <MetaRow label="Backend status">
          <StatusBadge value={query.data?.status} />
        </MetaRow>
        <MetaRow label="Database">
          <BoolBadge ok={query.data?.db} testId="settings-db-status" />
        </MetaRow>
        <MetaRow label="Redis">
          <BoolBadge ok={query.data?.redis} testId="settings-redis-status" />
        </MetaRow>
        <MetaRow label="Worker">
          <BoolBadge ok={query.data?.worker} testId="settings-worker-status" />
        </MetaRow>
        <MetaRow label="Frontend version">
          <code data-testid="settings-frontend-version">
            {FRONTEND_VERSION}
          </code>
        </MetaRow>
        <MetaRow label="Backend version">
          <code data-testid="settings-backend-version">
            {query.data?.version ?? "—"}
          </code>
        </MetaRow>
      </MetaList>
    </>
  );
}
