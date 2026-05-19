import { ReactNode } from "react";

export function MetaList({ children }: { children: ReactNode }) {
  return <div className="mt-4 flex flex-col gap-2">{children}</div>;
}

export function MetaRow({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="flex gap-4 text-sm">
      <span className="w-32 font-medium text-gray-600">{label}</span>
      <span>{children}</span>
    </div>
  );
}
