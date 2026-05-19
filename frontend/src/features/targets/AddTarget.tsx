import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ROUTES } from "../../app/routes";
import { PageHeader } from "../../components/PageHeader";
import { FormField, TextInput } from "../../components/Form";
import { Button } from "../../components/Button";
import { Callout } from "../../components/Callout";
import { useCreateTargetMutation } from "./api";
import { useCurrentProject } from "../../lib/useCurrentProject";
import { parseApiError } from "../../lib/parseApiError";
import { HttpError } from "../../lib/http";
import type { CreateTargetBody } from "../../types/api";

export function AddTarget() {
  const { id: projectId } = useCurrentProject();
  const [baseUrl, setBaseUrl] = useState("");
  const [host, setHost] = useState("");
  const [ip, setIp] = useState("");
  const [localBaseUrlError, setLocalBaseUrlError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [bannerError, setBannerError] = useState<string | null>(null);
  const navigate = useNavigate();
  const mutation = useCreateTargetMutation();

  if (!projectId) {
    return (
      <>
        <PageHeader title="Add target" />
        <div className="mt-4">
          <Callout variant="info" title="Select a project first">
            Open the Projects page and set one as current before adding a target.
          </Callout>
        </div>
      </>
    );
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!baseUrl.trim()) {
      setLocalBaseUrlError("base_url is required");
      return;
    }
    if (!/^https?:\/\//.test(baseUrl)) {
      setLocalBaseUrlError("base_url must start with http:// or https://");
      return;
    }
    setLocalBaseUrlError(null);
    setFieldErrors({});
    setBannerError(null);
    try {
      const body: CreateTargetBody = {
        project: projectId!,
        base_url: baseUrl,
      };
      const trimmedHost = host.trim();
      const trimmedIp = ip.trim();
      if (trimmedHost) body.host = trimmedHost;
      if (trimmedIp) body.ip = trimmedIp;
      await mutation.mutateAsync(body);
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
      <PageHeader title="Add target" />
      {bannerError && (
        <div className="mt-4">
          <Callout variant="error">{bannerError}</Callout>
        </div>
      )}
      <form
        onSubmit={onSubmit}
        noValidate
        className="mt-4 flex flex-col gap-4 max-w-lg"
      >
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
          />
        </FormField>
        <FormField label="IP" htmlFor="ip" error={fieldErrors.ip?.[0]}>
          <TextInput
            id="ip"
            value={ip}
            onChange={(e) => setIp(e.target.value)}
          />
        </FormField>
        <Button type="submit" loading={mutation.isPending}>
          Add target
        </Button>
      </form>
    </>
  );
}
