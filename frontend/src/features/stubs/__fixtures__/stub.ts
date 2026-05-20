import type { Stub, StubSummary } from "../../../types/api";

const BASE: StubSummary = {
  slug: "1.1",
  phase: 1,
  spec: 1,
  phase_slug: "01-information-gathering",
  spec_slug: "framework-detection",
  title: "Framework detection",
  phase_title: "Information gathering",
  category: "Content discovery",
  status: "done",
  fixture: "juice-shop",
  path: "01-information-gathering/01-framework-detection.md",
};

export function makeStub(overrides: Partial<StubSummary> = {}): StubSummary {
  return { ...BASE, ...overrides };
}

export function makeStubWithBody(
  overrides: Partial<Stub> = {},
): Stub {
  return {
    ...BASE,
    body: "# 1.1 Framework detection\n\nDetect the application framework.",
    ...overrides,
  };
}
