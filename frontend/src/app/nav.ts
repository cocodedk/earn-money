import {
  FolderKanban,
  Crosshair,
  ListChecks,
  Activity,
  AlertCircle,
  FileSearch,
  Settings as SettingsIcon,
  type LucideIcon,
} from "lucide-react";
import { ROUTES } from "./routes";

export type NavItem = {
  label: string;
  to: string;
  icon: LucideIcon;
  testid: string;
};

export const navItems: NavItem[] = [
  { label: "Projects", to: ROUTES.projects, icon: FolderKanban, testid: "nav-projects" },
  { label: "Targets", to: ROUTES.targets, icon: Crosshair, testid: "nav-targets" },
  { label: "Stubs", to: ROUTES.stubs, icon: ListChecks, testid: "nav-stubs" },
  { label: "Scan Runs", to: ROUTES.scanRuns, icon: Activity, testid: "nav-scan-runs" },
  { label: "Findings", to: ROUTES.findings, icon: AlertCircle, testid: "nav-findings" },
  { label: "Evidence", to: ROUTES.evidence, icon: FileSearch, testid: "nav-evidence" },
  { label: "Settings", to: ROUTES.settings, icon: SettingsIcon, testid: "nav-settings" },
];
