import { useSyncExternalStore } from "react";
import { ChevronsLeft, ChevronsRight } from "lucide-react";
import {
  setCollapsed,
  subscribeSidebar,
  getSnapshot,
} from "../../app/sidebar";
import styles from "./SidebarToggle.module.css";

export function SidebarToggle() {
  const snap = useSyncExternalStore(subscribeSidebar, getSnapshot, () => "false");
  const collapsed = snap === "true";
  return (
    <button
      type="button"
      className={styles.button}
      data-testid="sidebar-toggle"
      data-collapsed={String(collapsed)}
      aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      aria-expanded={!collapsed}
      aria-controls="primary-navigation"
      onClick={() => setCollapsed(!collapsed)}
    >
      {collapsed ? (
        <ChevronsRight size={16} aria-hidden focusable="false" />
      ) : (
        <ChevronsLeft size={16} aria-hidden focusable="false" />
      )}
    </button>
  );
}
