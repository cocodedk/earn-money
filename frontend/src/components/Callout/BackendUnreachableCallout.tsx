import { ReactNode } from "react";
import { Callout } from "./Callout";
import { BACKEND_UNREACHABLE } from "../../lib/messages";

export type BackendUnreachableCalloutProps = {
  children: ReactNode;
  // `() => unknown` so callers can pass `query.refetch` directly without
  // a `() => void` wrapper around its Promise return.
  onRetry?: () => unknown;
};

export function BackendUnreachableCallout({
  children,
  onRetry,
}: BackendUnreachableCalloutProps) {
  return (
    <Callout
      variant="error"
      title={BACKEND_UNREACHABLE}
      action={onRetry ? { label: "Retry", onClick: onRetry } : undefined}
    >
      {children}
    </Callout>
  );
}
