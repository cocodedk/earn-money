import type { Finding } from "../../../types/api";

export function makeFinding(over: Partial<Finding> = {}): Finding {
  return {
    id: "ffffffff-1111-1111-1111-111111111111",
    scan_run: "11111111-1111-1111-1111-111111111111",
    target: "22222222-2222-2222-2222-222222222222",
    stub_slug: "1.1-headers",
    title: "Missing security header",
    category: "headers",
    severity: "low",
    confidence: "medium",
    status: "candidate",
    data: {},
    created_at: "2026-05-20T08:00:00Z",
    updated_at: "2026-05-20T08:00:00Z",
    ...over,
  };
}
