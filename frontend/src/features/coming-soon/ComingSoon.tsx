import { PageHeader } from "../../components/PageHeader";

export type ComingSoonProps = { name: string };

export function ComingSoon({ name }: ComingSoonProps) {
  return (
    <>
      <PageHeader title={name} />
      <p className="mt-6 text-gray-600">Not built yet.</p>
    </>
  );
}
