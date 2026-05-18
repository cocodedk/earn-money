import { ROUTES } from "./routes";

export type NavItem = { label: string; to: string };

export const navItems: NavItem[] = [
  { label: "Projects", to: ROUTES.projects },
  { label: "Targets", to: ROUTES.targets },
  { label: "Stubs", to: ROUTES.stubs },
  { label: "Scan Runs", to: ROUTES.scanRuns },
  { label: "Findings", to: ROUTES.findings },
  { label: "Evidence", to: ROUTES.evidence },
  { label: "Settings", to: ROUTES.settings },
];
