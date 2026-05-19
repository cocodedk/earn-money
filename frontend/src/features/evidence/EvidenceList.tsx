import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { PageHeader } from "../../components/PageHeader";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import { Callout } from "../../components/Callout";
import {
  FiltersBar,
  type FilterDef,
} from "../../components/FiltersBar";
import { useEvidenceQuery, type EvidenceFilter } from "./api";
import { useProjectsQuery } from "../projects/api";
import { useTargetsQuery } from "../targets/api";
import { useScanRunsQuery } from "../scan-runs/api";
import { useCurrentProject } from "../../lib/useCurrentProject";
import type { Evidence } from "../../types/api";

const columns: TableColumn<Evidence>[] = [
  { key: "source", header: "Source", cell: (r) => r.source },
  {
    key: "target",
    header: "Target",
    cell: (r) => (
      <span className="font-mono text-xs">{r.target.slice(0, 8)}</span>
    ),
  },
  { key: "url", header: "URL", cell: (r) => r.url ?? "—" },
  { key: "method", header: "Method", cell: (r) => r.method ?? "—" },
  { key: "field", header: "Field", cell: (r) => r.field ?? "—" },
  {
    key: "matched_value",
    header: "Matched value",
    cell: (r) => (
      <Link
        to={`/evidence/${r.id}`}
        className="font-mono text-xs text-blue-700 hover:underline"
      >
        {r.matched_value ?? "—"}
      </Link>
    ),
  },
  {
    key: "created_at",
    header: "Created",
    cell: (r) => r.created_at.slice(0, 10),
  },
];

export function EvidenceList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { id: currentProjectId } = useCurrentProject();
  const projects = useProjectsQuery();
  const targets = useTargetsQuery(currentProjectId);
  const scanRuns = useScanRunsQuery(
    currentProjectId ? { project: currentProjectId } : {},
  );

  const filter: EvidenceFilter = useMemo(() => {
    const obj: Record<string, string> = {};
    for (const key of ["project", "target", "scan_run", "finding", "source"]) {
      const v = searchParams.get(key);
      if (v) obj[key] = v;
    }
    return obj as EvidenceFilter;
  }, [searchParams]);

  const query = useEvidenceQuery(filter);

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
    { key: "finding", label: "Finding (id)", options: [], inputType: "text" },
    { key: "source", label: "Source", options: [], inputType: "text" },
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
      <PageHeader title="Evidence" />
      <div className="mt-4 flex flex-col gap-4">
        <FiltersBar filters={filters} values={values} onChange={onChange} />
        {query.isError ? (
          <Callout
            variant="error"
            title="Backend unreachable"
            action={{ label: "Retry", onClick: () => void query.refetch() }}
          >
            Could not load evidence.
          </Callout>
        ) : (
          <Table<Evidence>
            columns={columns}
            rows={query.data?.results ?? []}
            rowKey={(r) => r.id}
            isLoading={query.isLoading}
            emptyState={<EmptyState message="No evidence yet." />}
          />
        )}
      </div>
    </>
  );
}
