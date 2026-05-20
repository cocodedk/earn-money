import type { ReactNode } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { Callout } from "../../../components/Callout";
import { Table, type TableColumn } from "../../../components/Table";
import type { Paginated } from "../../../types/api";

export type TargetSectionCopy = {
  // testid prefix → "<slug>-section", "<slug>-empty", "<slug>-loading", etc.
  slug: string;
  heading: string; // "Findings for target"
  errorMessage: string; // "Could not load findings."
  loadingMessage: string; // "Loading findings…"
  emptyMessage: string; // "No findings yet for this target."
  truncationNoun: string; // "findings" — used in "Showing first N of M <noun>"
};

export type TargetSectionProps<T extends { id: string }> = {
  query: UseQueryResult<Paginated<T>>;
  columns: TableColumn<T>[];
  rowTestIdPrefix: string; // "target-finding-row-"
  copy: TargetSectionCopy;
};

export function TargetSection<T extends { id: string }>({
  query,
  columns,
  rowTestIdPrefix,
  copy,
}: TargetSectionProps<T>): ReactNode {
  if (query.isError) {
    return <Callout variant="error">{copy.errorMessage}</Callout>;
  }
  if (!query.data) {
    return <div data-testid={`${copy.slug}-loading`}>{copy.loadingMessage}</div>;
  }
  const { results, count, next } = query.data;
  return (
    <section data-testid={`${copy.slug}-section`}>
      <h3>
        {copy.heading} ({count})
      </h3>
      {count === 0 ? (
        <p data-testid={`${copy.slug}-empty`}>{copy.emptyMessage}</p>
      ) : (
        <>
          <Table<T>
            columns={columns}
            rows={results}
            rowKey={(r) => r.id}
            rowTestId={(r) => `${rowTestIdPrefix}${r.id}`}
          />
          {next !== null && (
            <p data-testid={`${copy.slug}-truncation`}>
              Showing first {results.length} of {count} {copy.truncationNoun}
            </p>
          )}
        </>
      )}
    </section>
  );
}
