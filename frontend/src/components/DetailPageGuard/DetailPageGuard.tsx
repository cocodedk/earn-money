import { ReactElement, ReactNode } from "react";
import { Link } from "react-router-dom";
import { UseQueryResult } from "@tanstack/react-query";
import { PageHeader } from "../PageHeader";
import { BackendUnreachableCallout, Callout, CalloutSlot } from "../Callout";
import { isHttpStatus } from "../../lib/http";

export type DetailPageGuardOptions = {
  notFoundTitle: string;
  notFoundMessage: ReactNode;
  backTo: string;
  backLabel: string;
  errorTitle: string;
  errorBody: ReactNode;
  loadingTitle?: string;
};

export type DetailPageGuardProps<T> = {
  query: UseQueryResult<T>;
  options: DetailPageGuardOptions;
  children: (data: T) => ReactElement;
};

export function DetailPageGuard<T>({
  query,
  options,
  children,
}: DetailPageGuardProps<T>): ReactElement {
  if (isHttpStatus(query.error, 404)) {
    return (
      <>
        <PageHeader title={options.notFoundTitle} />
        <CalloutSlot>
          <Callout variant="info">
            {options.notFoundMessage}{" "}
            <Link to={options.backTo}>{options.backLabel}</Link>
          </Callout>
        </CalloutSlot>
      </>
    );
  }
  if (query.isError) {
    return (
      <>
        <PageHeader title={options.errorTitle} />
        <CalloutSlot>
          <BackendUnreachableCallout>
            {options.errorBody}
          </BackendUnreachableCallout>
        </CalloutSlot>
      </>
    );
  }
  if (!query.data) {
    return <PageHeader title={options.loadingTitle ?? "Loading…"} />;
  }
  return children(query.data);
}
