import { ChangeEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { useProjectsQuery } from "../projects/api";
import { useTargetsQuery } from "../targets/api";
import { useScanRunsQuery } from "../scan-runs/api";
import { useFindingsListQuery } from "../findings/api";

export const FILTER_PARAM_KEYS = [
  "project",
  "target",
  "scan_run",
  "finding",
  "source",
] as const;

export type FilterParamKey = (typeof FILTER_PARAM_KEYS)[number];

type Option = { value: string; label: string };
type SelectRow = {
  kind: "select";
  key: FilterParamKey;
  label: string;
  options: Option[];
};
type TextRow = {
  kind: "text";
  key: FilterParamKey;
  label: string;
  placeholder: string;
};
type FilterRow = SelectRow | TextRow;

function FilterSelect({
  filter,
  value,
  onChange,
}: {
  filter: SelectRow;
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <label className="flex flex-col text-sm">
      <span style={{ color: "var(--ink-muted)" }}>{filter.label}</span>
      <select
        aria-label={filter.label}
        value={value}
        onChange={(e: ChangeEvent<HTMLSelectElement>) =>
          onChange(e.target.value)
        }
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

function FilterText({
  filter,
  value,
  onChange,
}: {
  filter: TextRow;
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <label className="flex flex-col text-sm">
      <span style={{ color: "var(--ink-muted)" }}>{filter.label}</span>
      <input
        type="text"
        aria-label={filter.label}
        placeholder={filter.placeholder}
        value={value}
        onChange={(e: ChangeEvent<HTMLInputElement>) =>
          onChange(e.target.value)
        }
        data-testid={`filter-${filter.key}`}
      />
    </label>
  );
}

export function EvidenceFiltersBar() {
  const [params, setParams] = useSearchParams();
  const projects = useProjectsQuery();
  const targets = useTargetsQuery();
  const scanRuns = useScanRunsQuery();
  const findings = useFindingsListQuery({});

  const filters: FilterRow[] = [
    {
      kind: "select",
      key: "project",
      label: "Project",
      options: (projects.data?.results ?? []).map((p) => ({
        value: p.id,
        label: p.name,
      })),
    },
    {
      kind: "select",
      key: "target",
      label: "Target",
      options: (targets.data?.results ?? []).map((t) => ({
        value: t.id,
        label: t.base_url,
      })),
    },
    {
      kind: "select",
      key: "scan_run",
      label: "Scan run",
      options: (scanRuns.data?.results ?? []).map((r) => ({
        value: r.id,
        label: `${r.id.slice(0, 8)} (${r.stub_slug})`,
      })),
    },
    {
      kind: "select",
      key: "finding",
      label: "Finding",
      options: (findings.data?.results ?? []).map((f) => ({
        value: f.id,
        label: `${f.id.slice(0, 8)} — ${f.title}`,
      })),
    },
    {
      kind: "text",
      key: "source",
      label: "Source",
      placeholder: "e.g. http-headers",
    },
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
      data-testid="evidence-filters-bar"
    >
      {filters.map((f) =>
        f.kind === "select" ? (
          <FilterSelect
            key={f.key}
            filter={f}
            value={params.get(f.key) ?? ""}
            onChange={(v) => onChange(f.key, v)}
          />
        ) : (
          <FilterText
            key={f.key}
            filter={f}
            value={params.get(f.key) ?? ""}
            onChange={(v) => onChange(f.key, v)}
          />
        ),
      )}
    </div>
  );
}
