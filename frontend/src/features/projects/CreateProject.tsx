import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ROUTES } from "../../app/routes";
import { PageHeader } from "../../components/PageHeader";
import { FormField, TextInput, Textarea } from "../../components/Form";
import { Button } from "../../components/Button";
import { Callout } from "../../components/Callout";
import { useCreateProjectMutation } from "./api";
import { parseApiError } from "../../lib/parseApiError";
import { HttpError } from "../../lib/http";

export function CreateProject() {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [localNameError, setLocalNameError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [bannerError, setBannerError] = useState<string | null>(null);
  const navigate = useNavigate();
  const mutation = useCreateProjectMutation();

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      setLocalNameError("name is required");
      return;
    }
    setLocalNameError(null);
    setFieldErrors({});
    setBannerError(null);
    try {
      await mutation.mutateAsync({ name, description });
      navigate(ROUTES.projects);
    } catch (err) {
      const parsed = await parseApiError(
        err instanceof HttpError ? err.response : err,
      );
      if (parsed.kind === "field") {
        setFieldErrors(parsed.errors);
      } else if (parsed.kind === "non_field") {
        setBannerError(parsed.errors[0]);
      } else if (parsed.kind === "detail") {
        setBannerError(parsed.detail);
      } else if (parsed.kind === "server") {
        setBannerError("Something went wrong. Please try again.");
      } else {
        setBannerError("Backend unreachable.");
      }
    }
  }

  return (
    <>
      <PageHeader title="Create project" />
      {bannerError && (
        <div className="mt-4">
          <Callout variant="error">{bannerError}</Callout>
        </div>
      )}
      <form onSubmit={onSubmit} noValidate className="mt-4 flex flex-col gap-4 max-w-lg">
        <FormField
          label="Name"
          htmlFor="name"
          required
          error={localNameError ?? fieldErrors.name?.[0]}
        >
          <TextInput
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </FormField>
        <FormField
          label="Description"
          htmlFor="description"
          error={fieldErrors.description?.[0]}
        >
          <Textarea
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </FormField>
        <Button type="submit" loading={mutation.isPending}>
          Create project
        </Button>
      </form>
    </>
  );
}
