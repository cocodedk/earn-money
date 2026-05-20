import { ChangeEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { useProjectsQuery } from "../projects/api";
import { useStubsQuery } from "../stubs/api";
import type { ScanRun, ScanRunStatus } from "../../types/api";

const STATUSES: ScanRunStatus[] = [
  "queued",
  "running",
  "paused",
  "stopping",
  "stopped",
  "failed",
  "done",
];

export const SCAN_RUN_FILTER_KEYS = ["project", "stub", "status"] as const;
export type ScanRunFilterKey = (typeof SCAN_RUN_FILTER_KEYS)[number];

type Option = { value: string; label: string };
type FilterRow = { key: ScanRunFilterKey; label: string; options: Option[] };

function FilterSelect({
  filter,
  value,
  onChange,
}: {
  filter: FilterRow;
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <label className="flex flex-col text-sm">
      <span className="text-gray-600">{filter.label}</span>
      <select
        aria-label={filter.label}
        value={value}
        onChange={(e: ChangeEvent<HTMLSelectElement>) => onChange(e.target.value)}
        data-testid={`filter-${filter.key}`}
      >
        <option value="">All {filter.label.toLowerCase()}</option>
        {filter.options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function ScanRunsFiltersBar() {
  const [params, setParams] = useSearchParams();
  const projects = useProjectsQuery();
  const stubs = useStubsQuery();

  const filters: FilterRow[] = [
    {
      key: "project",
      label: "Project",
      options: (projects.data?.results ?? []).map((p) => ({
        value: p.id,
        label: p.name,
      })),
    },
    {
      key: "stub",
      label: "Stub",
      options: (stubs.data ?? []).map((s) => ({
        value: s.slug,
        label: s.slug,
      })),
    },
    {
      key: "status",
      label: "Status",
      options: STATUSES.map((s) => ({ value: s, label: s })),
    },
  ];

  function onChange(key: ScanRunFilterKey, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next);
  }

  return (
    <div className="flex flex-wrap gap-3" data-testid="scan-runs-filters-bar">
      {filters.map((f) => (
        <FilterSelect
          key={f.key}
          filter={f}
          value={params.get(f.key) ?? ""}
          onChange={(v) => onChange(f.key, v)}
        />
      ))}
    </div>
  );
}

export function applyScanRunFilters(
  runs: ScanRun[],
  params: URLSearchParams,
): ScanRun[] {
  const project = params.get("project");
  const stub = params.get("stub");
  const status = params.get("status");
  return runs.filter((r) => {
    if (project && r.project !== project) return false;
    if (stub && r.stub_slug !== stub) return false;
    if (status && r.status !== status) return false;
    return true;
  });
}
