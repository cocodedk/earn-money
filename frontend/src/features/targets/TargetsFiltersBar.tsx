import { ChangeEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { useProjectsQuery } from "../projects/api";
import type { Target, TargetStatus } from "../../types/api";

const STATUSES: TargetStatus[] = ["active", "retired"];

export const TARGET_FILTER_KEYS = ["project", "status"] as const;
export type TargetFilterKey = (typeof TARGET_FILTER_KEYS)[number];

type Option = { value: string; label: string };
type FilterRow = { key: TargetFilterKey; label: string; options: Option[] };

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

export function TargetsFiltersBar() {
  const [params, setParams] = useSearchParams();
  const projects = useProjectsQuery();

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
      key: "status",
      label: "Status",
      options: STATUSES.map((s) => ({ value: s, label: s })),
    },
  ];

  function onChange(key: TargetFilterKey, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next);
  }

  return (
    <div className="flex flex-wrap gap-3" data-testid="targets-filters-bar">
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

export function applyTargetFilters(
  targets: Target[],
  params: URLSearchParams,
): Target[] {
  const project = params.get("project");
  const status = params.get("status");
  return targets.filter((t) => {
    if (project && t.project !== project) return false;
    if (status && t.status !== status) return false;
    return true;
  });
}
