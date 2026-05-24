import { useMemo } from "react";
import { missionDetailPath } from "../../app/routes";
import { ButtonLink } from "../../components/Button";
import { PageHeader } from "../../components/PageHeader";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import { ListPageGuard } from "../../components/ListPageGuard";
import { useSessionsQuery } from "./api";
import type { AgentSession } from "./types";
import styles from "./MissionsList.module.css";

const STATUS_COLORS: Record<string, string> = {
  running: "ok",
  completed: "ok",
  failed: "err",
  stopped: "warn",
  pending: "muted",
  paused: "muted",
};

function StatusPill({ status }: { status: string }) {
  return (
    <span className={styles.status} data-color={STATUS_COLORS[status] ?? "muted"}>
      {status}
    </span>
  );
}

function phaseList(session: AgentSession): string {
  return session.active_phases
    .map((p) => (p === session.current_phase ? `[${p}]` : p))
    .join(" → ");
}

function budgetSummary(session: AgentSession): string {
  const used = session.consumed_budget?.mission?.turns
    ?? session.consumed_budget?.turns ?? 0;
  const max = session.mission_budget?.max_turns;
  return max != null ? `${used}/${max}` : `${used}`;
}

const COLUMNS: TableColumn<AgentSession>[] = [
  { key: "profile", header: "Mission", cell: (s) => s.mission_profile },
  { key: "target", header: "Target", cell: (s) => s.target_host },
  {
    key: "status",
    header: "Status",
    cell: (s) => <StatusPill status={s.status} />,
  },
  { key: "phase", header: "Phases", cell: (s) => phaseList(s) },
  { key: "turns", header: "Turns", cell: (s) => budgetSummary(s) },
  {
    key: "started",
    header: "Started",
    cell: (s) => (s.started_at ? s.started_at.slice(0, 19) : "—"),
  },
  {
    key: "actions",
    header: "",
    cell: (s) => (
      <ButtonLink to={missionDetailPath(s.id)} variant="secondary">
        View
      </ButtonLink>
    ),
  },
];

export function MissionsList() {
  const query = useSessionsQuery();
  const rows = useMemo(() => {
    const results = query.data?.results ?? [];
    return [...results].sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );
  }, [query.data]);

  return (
    <>
      <PageHeader title="Missions" />
      <ListPageGuard query={query} errorBody="Could not load missions.">
        <Table<AgentSession>
          columns={COLUMNS}
          rows={rows}
          rowKey={(s) => s.id}
          isLoading={query.isLoading}
          emptyState={<EmptyState message="No missions yet." />}
        />
      </ListPageGuard>
    </>
  );
}
