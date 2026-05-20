import { PageHeader } from "../../components/PageHeader";

export type ComingSoonProps = { name: string };

export function ComingSoon({ name }: ComingSoonProps) {
  return (
    <>
      <PageHeader title={name} />
      <p className="mt-6" style={{ color: "var(--ink-muted)" }}>
        Not built yet.
      </p>
    </>
  );
}
