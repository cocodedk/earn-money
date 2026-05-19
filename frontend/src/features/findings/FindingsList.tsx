import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { PageHeader } from "../../components/PageHeader";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import { Callout } from "../../components/Callout";
import { SeverityBadge } from "../../components/SeverityBadge";
import {
  FiltersBar,
  type FilterDef,
} from "../../components/FiltersBar";
import { useFindingsQuery, type FindingsFilter } from "./api";
import { useProjectsQuery } from "../projects/api";
import { useTargetsQuery } from "../targets/api";
import { useScanRunsQuery } from "../scan-runs/api";
import { useStubsQuery } from "../stubs/api";
import { useCurrentProject } from "../../lib/useCurrentProject";
import type {
  Confidence,
  Finding,
  FindingStatus,
  Severity,
} from "../../types/api";

const SEVERITIES: Severity[] = ["info", "low", "medium", "high", "critical"];
const CONFIDENCES: Confidence[] = ["low", "medium", "high"];
const STATUSES: FindingStatus[] = [
  "candidate",
  "confirmed",
  "rejected",
  "stale",
];

const columns: TableColumn<Finding>[] = [
  {
    key: "title",
    header: "Title",
    cell: (r) => (
      <Link to={`/findings/${r.id}`} className="text-blue-700 hover:underline">
        {r.title}
      </Link>
    ),
  },
  {
    key: "target",
    header: "Target",
    cell: (r) => (
      <span className="font-mono text-xs">{r.target.slice(0, 8)}</span>
    ),
  },
  { key: "stub_slug", header: "Stub", cell: (r) => r.stub_slug },
  { key: "category", header: "Category", cell: (r) => r.category },
  {
    key: "severity",
    header: "Severity",
    cell: (r) => <SeverityBadge severity={r.severity} />,
  },
  { key: "confidence", header: "Confidence", cell: (r) => r.confidence },
  { key: "status", header: "Status", cell: (r) => r.status },
  {
    key: "created_at",
    header: "Created",
    cell: (r) => r.created_at.slice(0, 10),
  },
];

export function FindingsList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { id: currentProjectId } = useCurrentProject();
  const projects = useProjectsQuery();
  const targets = useTargetsQuery(currentProjectId);
  const scanRuns = useScanRunsQuery(
    currentProjectId ? { project: currentProjectId } : {},
  );
  const stubs = useStubsQuery();

  const filter: FindingsFilter = useMemo(() => {
    const obj: Record<string, string> = {};
    for (const key of [
      "project",
      "target",
      "scan_run",
      "stub",
      "severity",
      "confidence",
      "status",
    ]) {
      const v = searchParams.get(key);
      if (v) obj[key] = v;
    }
    return obj as FindingsFilter;
  }, [searchParams]);

  const query = useFindingsQuery(filter);

  const filters: FilterDef[] = [
    {
      key: "project",
      label: "Project",
      options: (projects.data?.results ?? []).map((p) => ({
        value: p.id,
        label: p.name,
      })),
    },
    {
      key: "target",
      label: "Target",
      options: (targets.data?.results ?? []).map((t) => ({
        value: t.id,
        label: t.base_url,
      })),
    },
    {
      key: "scan_run",
      label: "Scan run",
      options: (scanRuns.data?.results ?? []).map((r) => ({
        value: r.id,
        label: `${r.id.slice(0, 8)} (${r.stub_slug})`,
      })),
    },
    {
      key: "stub",
      label: "Stub",
      options: (stubs.data ?? []).map((s) => ({
        value: s.slug,
        label: `${s.slug} — ${s.title}`,
      })),
    },
    {
      key: "severity",
      label: "Severity",
      options: SEVERITIES.map((s) => ({ value: s, label: s })),
    },
    {
      key: "confidence",
      label: "Confidence",
      options: CONFIDENCES.map((c) => ({ value: c, label: c })),
    },
    {
      key: "status",
      label: "Status",
      options: STATUSES.map((s) => ({ value: s, label: s })),
    },
  ];

  const values: Record<string, string> = Object.fromEntries(
    searchParams.entries(),
  );

  function onChange(key: string, value: string) {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next);
  }

  return (
    <>
      <PageHeader title="Findings" />
      <div className="mt-4 flex flex-col gap-4">
        <FiltersBar filters={filters} values={values} onChange={onChange} />
        {query.isError ? (
          <Callout
            variant="error"
            title="Backend unreachable"
            action={{ label: "Retry", onClick: () => void query.refetch() }}
          >
            Could not load findings.
          </Callout>
        ) : (
          <Table<Finding>
            columns={columns}
            rows={query.data?.results ?? []}
            rowKey={(r) => r.id}
            isLoading={query.isLoading}
            emptyState={<EmptyState message="No findings yet." />}
          />
        )}
      </div>
    </>
  );
}
