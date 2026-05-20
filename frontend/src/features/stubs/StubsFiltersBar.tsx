import { ChangeEvent, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import type { StubStatus, StubSummary } from "../../types/api";

const STATUSES: StubStatus[] = ["pending", "in-progress", "blocked", "done"];

export const STUB_FILTER_KEYS = ["phase", "status", "category"] as const;
export type StubFilterKey = (typeof STUB_FILTER_KEYS)[number];

type Option = { value: string; label: string };
type FilterRow = { key: StubFilterKey; label: string; options: Option[] };

function uniqueSorted<T>(values: T[], project: (v: T) => string): string[] {
  const seen = new Set<string>();
  for (const v of values) seen.add(project(v));
  return [...seen].sort();
}

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
      <span style={{ color: "var(--ink-muted)" }}>{filter.label}</span>
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

export function StubsFiltersBar({ stubs }: { stubs: StubSummary[] }) {
  const [params, setParams] = useSearchParams();

  const filters: FilterRow[] = useMemo(() => {
    const phases = uniqueSorted(stubs, (s) => String(s.phase));
    const categories = uniqueSorted(stubs, (s) => s.category).filter(Boolean);
    return [
      {
        key: "phase",
        label: "Phase",
        options: phases.map((p) => ({ value: p, label: p })),
      },
      {
        key: "status",
        label: "Status",
        options: STATUSES.map((s) => ({ value: s, label: s })),
      },
      {
        key: "category",
        label: "Category",
        options: categories.map((c) => ({ value: c, label: c })),
      },
    ];
  }, [stubs]);

  function onChange(key: StubFilterKey, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next);
  }

  return (
    <div className="flex flex-wrap gap-3" data-testid="stubs-filters-bar">
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

export function applyStubFilters(
  stubs: StubSummary[],
  params: URLSearchParams,
): StubSummary[] {
  const phase = params.get("phase");
  const status = params.get("status");
  const category = params.get("category");
  return stubs.filter((s) => {
    if (phase && String(s.phase) !== phase) return false;
    if (status && s.status !== status) return false;
    if (category && s.category !== category) return false;
    return true;
  });
}
