import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { stubDetailPath } from "../../app/routes";
import { ButtonLink } from "../../components/Button";
import { PageHeader } from "../../components/PageHeader";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import { ListPageGuard } from "../../components/ListPageGuard";
import { useStubsQuery } from "./api";
import { StatusBadge } from "./StatusBadge";
import { StubsFiltersBar, applyStubFilters } from "./StubsFiltersBar";
import type { StubSummary } from "../../types/api";

function buildColumns(): TableColumn<StubSummary>[] {
  return [
    { key: "phase", header: "Phase", cell: (s) => s.phase },
    { key: "spec", header: "Spec", cell: (s) => s.spec },
    {
      key: "slug",
      header: "Slug",
      cell: (s) => <Link to={stubDetailPath(s.slug)}>{s.slug}</Link>,
    },
    {
      key: "spec_slug",
      header: "Spec slug",
      cell: (s) => s.spec_slug || "—",
    },
    { key: "title", header: "Title", cell: (s) => s.title },
    {
      key: "status",
      header: "Status",
      cell: (s) => <StatusBadge status={s.status} />,
    },
    { key: "fixture", header: "Fixture", cell: (s) => s.fixture },
    {
      key: "actions",
      header: "Actions",
      cell: (s) => (
        <ButtonLink to={stubDetailPath(s.slug)} variant="secondary">
          View
        </ButtonLink>
      ),
    },
  ];
}

export function StubsList() {
  const query = useStubsQuery();
  const [params] = useSearchParams();
  const columns = useMemo(buildColumns, []);
  const stubs = query.data ?? [];
  const filtered = useMemo(
    () => applyStubFilters(stubs, params),
    [stubs, params],
  );
  return (
    <>
      <PageHeader title="Stubs" />
      <StubsFiltersBar stubs={stubs} />
      <ListPageGuard query={query} errorBody="Could not load stubs.">
        <Table<StubSummary>
          columns={columns}
          rows={filtered}
          rowKey={(s) => s.slug}
          isLoading={query.isLoading}
          emptyState={
            <EmptyState
              message={
                stubs.length === 0
                  ? "No stubs found."
                  : "No stubs match the current filters."
              }
            />
          }
        />
      </ListPageGuard>
    </>
  );
}
