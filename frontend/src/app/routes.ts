export const ROUTES = {
  index: "/",
  projects: "/projects",
  projectsNew: "/projects/new",
  targets: "/targets",
  targetsNew: "/targets/new",
  stubs: "/stubs",
  stubDetail: "/stubs/:slug",
  scanRuns: "/scan-runs",
  findings: "/findings",
  evidence: "/evidence",
  settings: "/settings",
} as const;

export const stubDetailPath = (slug: string) => `/stubs/${slug}`;
