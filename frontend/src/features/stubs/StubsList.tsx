import { useMemo } from "react";
import { Link } from "react-router-dom";
import { stubDetailPath } from "../../app/routes";
import { ButtonLink } from "../../components/Button";
import { PageHeader } from "../../components/PageHeader";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import { Callout } from "../../components/Callout";
import { useStubsQuery } from "./api";
import { StatusBadge } from "./StatusBadge";
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
  const columns = useMemo(buildColumns, []);
  return (
    <>
      <PageHeader title="Stubs" />
      <div className="mt-4">
        {query.isError ? (
          <Callout
            variant="error"
            title="Backend unreachable"
            action={{ label: "Retry", onClick: () => void query.refetch() }}
          >
            Could not load stubs.
          </Callout>
        ) : (
          <Table<StubSummary>
            columns={columns}
            rows={query.data ?? []}
            rowKey={(s) => s.slug}
            isLoading={query.isLoading}
            emptyState={<EmptyState message="No stubs found." />}
          />
        )}
      </div>
    </>
  );
}
