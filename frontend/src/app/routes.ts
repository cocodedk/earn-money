export const ROUTES = {
  index: "/",
  projects: "/projects",
  projectsNew: "/projects/new",
  targets: "/targets",
  targetsNew: "/targets/new",
  stubs: "/stubs",
  scanRuns: "/scan-runs",
  scanRunsNew: "/scan-runs/new",
  scanRunDetail: (id: string) => `/scan-runs/${id}`,
  findings: "/findings",
  evidence: "/evidence",
  settings: "/settings",
} as const;
