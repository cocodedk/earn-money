import { Link } from "react-router-dom";
import { ROUTES } from "../../app/routes";
import { FormField } from "../../components/Form";
import { Callout, CalloutSlot } from "../../components/Callout";
import { useProjectsQuery } from "./api";

export type ProjectPickerFieldProps = {
  value: string;
  onChange: (id: string) => void;
  error?: string;
};

export function ProjectPickerField({
  value,
  onChange,
  error,
}: ProjectPickerFieldProps) {
  const projects = useProjectsQuery();
  const rows = projects.data?.results ?? [];
  const isEmpty = projects.isSuccess && rows.length === 0;
  const disabled = projects.isLoading || projects.isError || isEmpty;
  return (
    <>
      {projects.isError && (
        <CalloutSlot>
          <Callout variant="error">Could not load projects.</Callout>
        </CalloutSlot>
      )}
      {isEmpty && (
        <CalloutSlot>
          <Callout variant="info">
            <Link to={ROUTES.projectsNew}>Create a project first.</Link>
          </Callout>
        </CalloutSlot>
      )}
      <FormField label="Project" htmlFor="project" required error={error}>
        <select
          id="project"
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          className="rounded px-3 py-2 text-sm"
          style={{ border: "1px solid var(--rule-soft)" }}
        >
          <option value="">
            {projects.isLoading ? "Loading projects…" : "Select a project…"}
          </option>
          {rows.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </FormField>
    </>
  );
}
