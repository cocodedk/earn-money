import { ChangeEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { useProjectsQuery } from "../projects/api";
import { useTargetsQuery } from "../targets/api";
import { useScanRunsQuery } from "../scan-runs/api";
import { useStubsQuery } from "../stubs/api";
import type {
  Confidence,
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

export const FILTER_PARAM_KEYS = [
  "project",
  "target",
  "scan_run",
  "stub_slug",
  "severity",
  "confidence",
  "status",
] as const;

export type FilterParamKey = (typeof FILTER_PARAM_KEYS)[number];

type Option = { value: string; label: string };
type FilterRow = { key: FilterParamKey; label: string; options: Option[] };

function literalOpts<T extends string>(values: readonly T[]): Option[] {
  return values.map((v) => ({ value: v, label: v }));
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

export function FindingsFiltersBar() {
  const [params, setParams] = useSearchParams();
  const projects = useProjectsQuery();
  const targets = useTargetsQuery();
  const scanRuns = useScanRunsQuery();
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
      key: "stub_slug",
      label: "Stub",
      options: (stubs.data ?? []).map((s) => ({
        value: s.slug,
        label: `${s.slug} — ${s.title}`,
      })),
    },
    { key: "severity", label: "Severity", options: literalOpts(SEVERITIES) },
    {
      key: "confidence",
      label: "Confidence",
      options: literalOpts(CONFIDENCES),
    },
    { key: "status", label: "Status", options: literalOpts(STATUSES) },
  ];

  function onChange(key: FilterParamKey, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next);
  }

  return (
    <div
      className="flex flex-wrap gap-3"
      data-testid="findings-filters-bar"
    >
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
