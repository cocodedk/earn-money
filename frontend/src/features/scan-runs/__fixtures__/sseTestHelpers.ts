import { waitFor } from "@testing-library/react";
import { MockEventSource } from "../../../test/sseMock";

export const RUN_A = "11111111-1111-1111-1111-111111111111";
export const RUN_B = "22222222-2222-2222-2222-222222222222";

export function lastInstance(): MockEventSource {
  const arr = MockEventSource.instances;
  return arr[arr.length - 1];
}

export async function waitConnected(result: {
  current: { status: string };
}): Promise<void> {
  await waitFor(() => {
    if (result.current.status !== "connected") {
      throw new Error(`status=${result.current.status}`);
    }
  });
}
