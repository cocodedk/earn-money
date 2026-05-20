import type { Evidence } from "../../../types/api";

export function makeEvidence(over: Partial<Evidence> = {}): Evidence {
  return {
    id: "eeeeeeee-2222-2222-2222-222222222222",
    scan_run: "11111111-1111-1111-1111-111111111111",
    target: "22222222-2222-2222-2222-222222222222",
    finding: null,
    source: "http-headers",
    url: "https://target.cocode.dk/",
    method: "GET",
    field: "X-Frame-Options",
    matched_value: "ALLOWALL",
    raw_excerpt: null,
    content_hash: "abc123",
    data: {},
    created_at: "2026-05-20T08:00:00Z",
    ...over,
  };
}
