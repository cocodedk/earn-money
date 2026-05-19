import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ROUTES } from "../../app/routes";
import { PageHeader } from "../../components/PageHeader";
import { FormField, TextInput } from "../../components/Form";
import { Button } from "../../components/Button";
import { Callout, CalloutSlot } from "../../components/Callout";
import { ProjectPickerField } from "../projects/ProjectPickerField";
import { useCreateTargetMutation } from "./api";
import { parseApiError } from "../../lib/parseApiError";
import { applyParsedError } from "../../lib/applyParsedError";
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

type FormState = {
  projectId: string;
  baseUrl: string;
  host: string;
  ip: string;
};

function buildBody(state: FormState): CreateTargetBody {
  return {
    project: state.projectId,
    base_url: state.baseUrl.trim(),
    ...(state.host.trim() ? { host: state.host.trim() } : {}),
    ...(state.ip.trim() ? { ip: state.ip.trim() } : {}),
  };
}

export function CreateTarget() {
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

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const urlError = validateBaseUrl(baseUrl);
    setLocalBaseUrlError(urlError);
    if (urlError) return;
    setFieldErrors({});
    setBannerError(null);
    try {
      await mutation.mutateAsync(buildBody({ projectId, baseUrl, host, ip }));
      navigate(ROUTES.targets);
    } catch (err) {
      applyParsedError(await parseApiError(err), {
        setFieldErrors,
        setBannerError,
      });
    }
  }

  return (
    <>
      <PageHeader title="Create target" />
      {bannerError && (
        <CalloutSlot>
          <Callout variant="error">{bannerError}</Callout>
        </CalloutSlot>
      )}
      <form
        onSubmit={onSubmit}
        noValidate
        className="mt-4 flex flex-col gap-4 max-w-lg"
      >
        <ProjectPickerField
          value={projectId}
          onChange={setProjectId}
          error={fieldErrors.project?.[0]}
        />
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
