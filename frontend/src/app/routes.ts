export const ROUTES = {
  index: "/",
  projects: "/projects",
  projectsNew: "/projects/new",
  targets: "/targets",
  targetsNew: "/targets/new",
  targetResult: "/targets/:targetId/results",
  stubs: "/stubs",
  stubDetail: "/stubs/:slug",
  scanRuns: "/scan-runs",
  scanRunsNew: "/scan-runs/new",
  scanRunDetail: "/scan-runs/:id",
  findings: "/findings",
  findingDetail: "/findings/:findingId",
  evidence: "/evidence",
  evidenceDetail: "/evidence/:evidenceId",
  settings: "/settings",
  missions: "/missions",
  missionDetail: "/missions/:sessionId",
} as const;

export const stubDetailPath = (slug: string) => `/stubs/${slug}`;
export const scanRunDetailPath = (id: string) => `/scan-runs/${id}`;
export const targetResultPath = (id: string) => `/targets/${id}/results`;
export const findingDetailPath = (id: string) => `/findings/${id}`;
export const evidenceDetailPath = (id: string) => `/evidence/${id}`;
export const missionDetailPath = (sessionId: string) => `/missions/${encodeURIComponent(sessionId)}`;
