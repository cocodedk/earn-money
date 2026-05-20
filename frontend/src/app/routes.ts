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
  evidence: "/evidence",
  settings: "/settings",
} as const;

export const stubDetailPath = (slug: string) => `/stubs/${slug}`;
export const scanRunDetailPath = (id: string) => `/scan-runs/${id}`;
export const targetResultPath = (id: string) => `/targets/${id}/results`;
