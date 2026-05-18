import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ROUTES } from "../../app/routes";
import { PageHeader } from "../../components/PageHeader";
import { FormField } from "../../components/Form";
import { Button } from "../../components/Button";
import { Callout } from "../../components/Callout";
import {
  useCreateScanRunMutation,
  useScanRunLifecycleMutation,
} from "./api";
import { useTargetsQuery } from "../targets/api";
import { useStubsQuery } from "../stubs/api";
import { useCurrentProject } from "../../lib/useCurrentProject";
import { parseApiError } from "../../lib/parseApiError";
import { HttpError } from "../../lib/http";

type SubmitMode = "create" | "create-and-start";

export function CreateScanRun() {
  const { id: projectId } = useCurrentProject();
  const targetsQuery = useTargetsQuery(projectId);
  const stubsQuery = useStubsQuery();
  const [selectedTargetIds, setSelectedTargetIds] = useState<string[] | null>(
    null,
  );
  const [stubSlug, setStubSlug] = useState<string>("");
  const [targetsError, setTargetsError] = useState<string | null>(null);
  const [bannerError, setBannerError] = useState<string | null>(null);
  const navigate = useNavigate();
  const create = useCreateScanRunMutation();

  const activeTargets = (targetsQuery.data?.results ?? []).filter(
    (t) => t.status === "active",
  );

  // Default to "all active" the first time targets land.
  useEffect(() => {
    if (selectedTargetIds === null && activeTargets.length > 0) {
      setSelectedTargetIds(activeTargets.map((t) => t.id));
    }
  }, [selectedTargetIds, activeTargets]);

  useEffect(() => {
    if (stubSlug === "" && stubsQuery.data && stubsQuery.data.length > 0) {
      setStubSlug(stubsQuery.data[0].slug);
    }
  }, [stubSlug, stubsQuery.data]);

  if (!projectId) {
    return (
      <>
        <PageHeader title="Create scan run" />
        <div className="mt-4">
          <Callout variant="info" title="Select a project first">
            Open the Projects page and set one as current before creating a scan run.
          </Callout>
        </div>
      </>
    );
  }

  const checked = selectedTargetIds ?? [];

  function toggleTarget(id: string) {
    const current = selectedTargetIds ?? [];
    setSelectedTargetIds(
      current.includes(id)
        ? current.filter((x) => x !== id)
        : [...current, id],
    );
  }

  function selectAll() {
    setSelectedTargetIds(activeTargets.map((t) => t.id));
  }

  function clearAll() {
    setSelectedTargetIds([]);
  }

  async function submit(mode: SubmitMode) {
    if (checked.length === 0) {
      setTargetsError("at least one target is required");
      return;
    }
    setTargetsError(null);
    setBannerError(null);
    try {
      const run = await create.mutateAsync({
        project: projectId!,
        stub_slug: stubSlug,
        target_ids: checked,
      });
      if (mode === "create-and-start") {
        await fetch(`/api/scan-runs/${run.id}/start/`, { method: "POST" });
      }
      navigate(ROUTES.scanRunDetail(run.id));
    } catch (err) {
      const parsed = await parseApiError(
        err instanceof HttpError ? err.response : err,
      );
      if (parsed.kind === "non_field") setBannerError(parsed.errors[0]);
      else if (parsed.kind === "detail") setBannerError(parsed.detail);
      else if (parsed.kind === "server")
        setBannerError("Something went wrong. Please try again.");
      else if (parsed.kind === "network") setBannerError("Backend unreachable.");
      else setBannerError("Could not create scan run.");
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void submit("create");
  }

  return (
    <>
      <PageHeader title="Create scan run" />
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
        <FormField label="Stub" htmlFor="stub_slug">
          <select
            id="stub_slug"
            value={stubSlug}
            onChange={(e) => setStubSlug(e.target.value)}
            className="h-10 px-3 rounded border border-gray-300 bg-white text-sm"
          >
            {(stubsQuery.data ?? []).map((s) => (
              <option key={s.slug} value={s.slug}>
                {s.slug} — {s.title}
              </option>
            ))}
          </select>
        </FormField>
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-900">Targets</span>
            <div className="flex items-center gap-2 text-sm">
              <button
                type="button"
                onClick={selectAll}
                className="text-blue-700 hover:underline"
              >
                Select all
              </button>
              <span className="text-gray-300">·</span>
              <button
                type="button"
                onClick={clearAll}
                className="text-blue-700 hover:underline"
              >
                Clear all
              </button>
            </div>
          </div>
          <ul className="flex flex-col gap-2 border border-gray-200 rounded p-3">
            {activeTargets.map((t) => (
              <li key={t.id}>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={checked.includes(t.id)}
                    onChange={() => toggleTarget(t.id)}
                  />
                  {t.base_url}
                </label>
              </li>
            ))}
          </ul>
          {targetsError && (
            <p className="text-sm text-red-700">{targetsError}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button type="submit" loading={create.isPending}>
            Create scan run
          </Button>
          <Button
            type="button"
            variant="secondary"
            loading={create.isPending}
            onClick={() => void submit("create-and-start")}
          >
            Create and start
          </Button>
        </div>
      </form>
    </>
  );
}
