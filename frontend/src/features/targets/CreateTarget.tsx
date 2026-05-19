import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ROUTES } from "../../app/routes";
import { PageHeader } from "../../components/PageHeader";
import { FormField, TextInput } from "../../components/Form";
import { Button } from "../../components/Button";
import { Callout } from "../../components/Callout";
import { useProjectsQuery } from "../projects/api";
import { useCreateTargetMutation } from "./api";
import { parseApiError } from "../../lib/parseApiError";
import { HttpError } from "../../lib/http";
import type { CreateTargetBody } from "../../types/api";

const SCHEME_AUTHORITY = /^https?:\/\/[^/\s]+/i;

function validateBaseUrl(raw: string): string | null {
  const value = raw.trim();
  if (!value) return "base_url is required";
  if (!SCHEME_AUTHORITY.test(value)) {
    return "base_url must start with http:// or https:// and include a host";
  }
  try {
    // Defensive parse — covers inputs the scheme/authority regex
    // accepts but WHATWG URL parsing rejects (e.g. unclosed IPv6 brackets).
    new URL(value);
  } catch {
    return "Enter a valid URL like https://example.com";
  }
  return null;
}

function buildBody(
  projectId: string,
  baseUrl: string,
  host: string,
  ip: string,
): CreateTargetBody {
  return {
    project: projectId,
    base_url: baseUrl.trim(),
    ...(host.trim() ? { host: host.trim() } : {}),
    ...(ip.trim() ? { ip: ip.trim() } : {}),
  };
}

export function CreateTarget() {
  const projects = useProjectsQuery();
  const mutation = useCreateTargetMutation();
  const navigate = useNavigate();

  const [projectId, setProjectId] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [host, setHost] = useState("");
  const [ip, setIp] = useState("");
  const [localBaseUrlError, setLocalBaseUrlError] = useState<string | null>(
    null,
  );
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [bannerError, setBannerError] = useState<string | null>(null);

  const isProjectsEmpty =
    projects.isSuccess && projects.data?.results.length === 0;
  const projectSelectDisabled =
    projects.isLoading || projects.isError || isProjectsEmpty;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const urlError = validateBaseUrl(baseUrl);
    setLocalBaseUrlError(urlError);
    if (urlError) return;
    setFieldErrors({});
    setBannerError(null);
    try {
      await mutation.mutateAsync(buildBody(projectId, baseUrl, host, ip));
      navigate(ROUTES.targets);
    } catch (err) {
      const parsed = await parseApiError(
        err instanceof HttpError ? err.response : err,
      );
      if (parsed.kind === "field") setFieldErrors(parsed.errors);
      else if (parsed.kind === "non_field") setBannerError(parsed.errors[0]);
      else if (parsed.kind === "detail") setBannerError(parsed.detail);
      else if (parsed.kind === "server")
        setBannerError("Something went wrong. Please try again.");
      else setBannerError("Backend unreachable.");
    }
  }

  return (
    <>
      <PageHeader title="Create target" />
      {bannerError && (
        <div className="mt-4">
          <Callout variant="error">{bannerError}</Callout>
        </div>
      )}
      {projects.isError && (
        <div className="mt-4">
          <Callout variant="error">Could not load projects.</Callout>
        </div>
      )}
      {isProjectsEmpty && (
        <div className="mt-4">
          <Callout variant="info">
            <Link to={ROUTES.projectsNew}>Create a project first.</Link>
          </Callout>
        </div>
      )}
      <form
        onSubmit={onSubmit}
        noValidate
        className="mt-4 flex flex-col gap-4 max-w-lg"
      >
        <FormField
          label="Project"
          htmlFor="project"
          required
          error={fieldErrors.project?.[0]}
        >
          <select
            id="project"
            value={projectId}
            disabled={projectSelectDisabled}
            onChange={(e) => setProjectId(e.target.value)}
            className="rounded border border-gray-300 px-3 py-2 text-sm"
          >
            <option value="">
              {projects.isLoading ? "Loading projects…" : "Select a project…"}
            </option>
            {(projects.data?.results ?? []).map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </FormField>
        <FormField
          label="Base URL"
          htmlFor="base_url"
          required
          error={localBaseUrlError ?? fieldErrors.base_url?.[0]}
        >
          <TextInput
            id="base_url"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
          />
        </FormField>
        <FormField label="Host" htmlFor="host" error={fieldErrors.host?.[0]}>
          <TextInput
            id="host"
            value={host}
            onChange={(e) => setHost(e.target.value)}
            placeholder="Leave blank to auto-derive from base URL"
          />
        </FormField>
        <FormField label="IP" htmlFor="ip" error={fieldErrors.ip?.[0]}>
          <TextInput
            id="ip"
            value={ip}
            onChange={(e) => setIp(e.target.value)}
            placeholder="Leave blank if unknown"
          />
        </FormField>
        <Button type="submit" loading={mutation.isPending}>
          Create target
        </Button>
      </form>
    </>
  );
}
