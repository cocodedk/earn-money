export type NavItem = { label: string; to: string };

export const navItems: NavItem[] = [
  { label: "Projects", to: "/projects" },
  { label: "Targets", to: "/targets" },
  { label: "Stubs", to: "/stubs" },
  { label: "Scan Runs", to: "/scan-runs" },
  { label: "Findings", to: "/findings" },
  { label: "Evidence", to: "/evidence" },
  { label: "Settings", to: "/settings" },
];
