import { ReactNode } from "react";
import { Callout } from "./Callout";
import { BACKEND_UNREACHABLE } from "../../lib/applyParsedError";

export type BackendUnreachableCalloutProps = {
  children: ReactNode;
  onRetry?: () => void;
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
