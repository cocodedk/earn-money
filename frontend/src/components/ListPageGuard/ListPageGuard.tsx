import { ReactNode } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { BackendUnreachableCallout } from "../Callout";

export type ListPageGuardProps = {
  query: Pick<UseQueryResult<unknown>, "isError" | "refetch">;
  errorBody: ReactNode;
  children: ReactNode;
};

export function ListPageGuard({
  query,
  errorBody,
  children,
}: ListPageGuardProps) {
  return (
    <div className="mt-4">
      {query.isError ? (
        <BackendUnreachableCallout onRetry={query.refetch}>
          {errorBody}
        </BackendUnreachableCallout>
      ) : (
        children
      )}
    </div>
  );
}
