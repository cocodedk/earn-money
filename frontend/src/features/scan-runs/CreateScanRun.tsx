import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ROUTES } from "../../app/routes";
import { PageHeader } from "../../components/PageHeader";
import { FormField } from "../../components/Form";
import { Button } from "../../components/Button";
import { Callout, CalloutSlot } from "../../components/Callout";
import { useProjectsQuery } from "../projects/api";
import { useTargetsQuery } from "../targets/api";
import { useStubsQuery } from "../stubs/api";
import {
  useCreateScanRunMutation,
  useStartScanRunMutation,
} from "./api";
import { parseApiError } from "../../lib/parseApiError";
import { applyParsedError } from "../../lib/applyParsedError";
import type { CreateScanRunBody, Target } from "../../types/api";

type PickerMode = "all" | "selected";

export function CreateScanRun() {
  const projects = useProjectsQuery();
  const stubs = useStubsQuery();
  const targets = useTargetsQuery();
  const createMutation = useCreateScanRunMutation();
  const startMutation = useStartScanRunMutation();
  const navigate = useNavigate();

  const [projectId, setProjectId] = useState("");
  const [stubSlug, setStubSlug] = useState("");
  const [pickerMode, setPickerMode] = useState<PickerMode>("all");
  const [selectedTargetIds, setSelectedTargetIds] = useState<string[]>([]);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [bannerError, setBannerError] = useState<string | null>(null);
  const [startLegError, setStartLegError] = useState<string | null>(null);

  const activeTargets: Target[] = useMemo(
    () =>
      (targets.data?.results ?? []).filter(
        (t) => t.project === projectId && t.status === "active",
      ),
    [targets.data?.results, projectId],
  );

  const targetIds =
    pickerMode === "all"
      ? activeTargets.map((t) => t.id)
      : selectedTargetIds;

  const isProjectsEmpty =
    projects.isSuccess && projects.data?.results.length === 0;

  async function submitForm(chainStart: boolean) {
    setFieldErrors({});
    setBannerError(null);
    setStartLegError(null);
    if (!projectId) {
      setFieldErrors({ project: ["project is required"] });
      return;
    }
    if (!stubSlug) {
      setFieldErrors({ stub_slug: ["stub is required"] });
      return;
    }
    if (targetIds.length === 0) {
      setFieldErrors({ target_ids: ["at least one target is required"] });
      return;
    }
    const body: CreateScanRunBody = {
      project: projectId,
      stub_slug: stubSlug,
      target_ids: targetIds,
    };
    try {
      const run = await createMutation.mutateAsync(body);
      if (chainStart) {
        try {
          await startMutation.mutateAsync(run.id);
        } catch (err) {
          // Create succeeded, start failed. Keep the operator on the
          // form so the error stays visible; the queued run is already
          // in the list (peer's micro-nit) and the row's Start button
          // is the retry path. Operator navigates manually when ready.
          const parsed = await parseApiError(err);
          setStartLegError(
            parsed.kind === "detail"
              ? parsed.detail
              : "Could not start the scan run.",
          );
          return;
        }
      }
      navigate(ROUTES.scanRuns);
    } catch (err) {
      applyParsedError(await parseApiError(err), {
        setFieldErrors,
        setBannerError,
      });
    }
  }

  function toggleSelected(targetId: string) {
    setSelectedTargetIds((prev) =>
      prev.includes(targetId)
        ? prev.filter((id) => id !== targetId)
        : [...prev, targetId],
    );
  }

  return (
    <>
      <PageHeader title="Create scan run" />
      {bannerError && (
        <CalloutSlot>
          <Callout variant="error">{bannerError}</Callout>
        </CalloutSlot>
      )}
      {startLegError && (
        <CalloutSlot>
          <Callout variant="warning" title="Run created but could not start">
            {startLegError}
          </Callout>
        </CalloutSlot>
      )}
      {stubs.isError && (
        <CalloutSlot>
          <Callout variant="error">Could not load stubs.</Callout>
        </CalloutSlot>
      )}
      {isProjectsEmpty && (
        <CalloutSlot>
          <Callout variant="info">
            <Link to={ROUTES.projectsNew}>Create a project first.</Link>
          </Callout>
        </CalloutSlot>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void submitForm(false);
        }}
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
            disabled={projects.isLoading || projects.isError || isProjectsEmpty}
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
          label="Stub"
          htmlFor="stub_slug"
          required
          error={fieldErrors.stub_slug?.[0]}
        >
          <select
            id="stub_slug"
            value={stubSlug}
            disabled={stubs.isLoading || stubs.isError}
            onChange={(e) => setStubSlug(e.target.value)}
            className="rounded border border-gray-300 px-3 py-2 text-sm"
          >
            <option value="">
              {stubs.isLoading ? "Loading stubs…" : "Select a stub…"}
            </option>
            {(stubs.data ?? []).map((s) => (
              <option key={s.slug} value={s.slug}>
                {s.slug} · {s.title}
              </option>
            ))}
          </select>
        </FormField>
        <FormField
          label="Targets"
          htmlFor="picker_mode"
          required
          error={fieldErrors.target_ids?.[0]}
        >
          <div id="picker_mode" className="flex flex-col gap-2">
            {projectId && activeTargets.length === 0 && (
              <p className="text-sm text-gray-600">
                No active targets for this project.
              </p>
            )}
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="picker_mode"
                checked={pickerMode === "all"}
                onChange={() => setPickerMode("all")}
              />
              All active project targets ({activeTargets.length})
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="picker_mode"
                checked={pickerMode === "selected"}
                onChange={() => setPickerMode("selected")}
              />
              Selected targets only
            </label>
            {pickerMode === "selected" && (
              <ul className="ml-6 flex flex-col gap-1">
                {activeTargets.length === 0 && (
                  <li className="text-sm text-gray-600">No active targets.</li>
                )}
                {activeTargets.map((t) => (
                  <li key={t.id}>
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={selectedTargetIds.includes(t.id)}
                        onChange={() => toggleSelected(t.id)}
                      />
                      {t.id} · {t.base_url}
                    </label>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </FormField>
        <div className="flex gap-2">
          <Button type="submit" loading={createMutation.isPending}>
            Create scan run
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={() => void submitForm(true)}
            loading={createMutation.isPending || startMutation.isPending}
          >
            Create and start
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={() => navigate(ROUTES.scanRuns)}
          >
            Cancel
          </Button>
        </div>
      </form>
    </>
  );
}
