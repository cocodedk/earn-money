import { ReactNode } from "react";

// Spacing wrapper for Callouts sitting under a PageHeader — keeps the
// `mt-4` token in one place so the gap stays consistent across forms.
export function CalloutSlot({ children }: { children: ReactNode }) {
  return <div className="mt-4">{children}</div>;
}
