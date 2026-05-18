import { useNavigate } from "react-router-dom";
import { ButtonLink } from "../../components/Button";
import { PageHeader } from "../../components/PageHeader";
import { Table, type TableColumn } from "../../components/Table";
import { EmptyState } from "../../components/EmptyState";
import { Callout } from "../../components/Callout";
import { useProjectsQuery } from "./api";
import type { Project } from "../../types/api";

const columns: TableColumn<Project>[] = [
  { key: "name", header: "Name", cell: (r) => r.name },
  { key: "description", header: "Description", cell: (r) => r.description },
  { key: "target_count", header: "Target count", cell: (r) => r.target_count },
  { key: "scan_run_count", header: "Scan run count", cell: (r) => r.scan_run_count },
  { key: "created_at", header: "Created at", cell: (r) => r.created_at.slice(0, 10) },
];

export function ProjectsList() {
  const query = useProjectsQuery();
  const navigate = useNavigate();
  return (
    <>
      <PageHeader
        title="Projects"
        action={
          <ButtonLink to="/projects/new" data-testid="page-header-create">
            Create project
          </ButtonLink>
        }
      />
      {query.isError ? (
        <div className="mt-4">
          <Callout
            variant="error"
            title="Backend unreachable"
            action={{ label: "Retry", onClick: () => void query.refetch() }}
          >
            Could not load projects.
          </Callout>
        </div>
      ) : (
        <div className="mt-4">
          <Table<Project>
            columns={columns}
            rows={query.data?.results ?? []}
            rowKey={(r) => r.id}
            isLoading={query.isLoading}
            emptyState={
              <EmptyState
                message="No projects yet."
                action={{
                  label: "Create project",
                  onClick: () => navigate("/projects/new"),
                }}
              />
            }
          />
        </div>
      )}
    </>
  );
}
