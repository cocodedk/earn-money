import { useSyncExternalStore } from "react";
import { NavLink, Outlet } from "react-router-dom";
import styles from "./Layout.module.css";
import { navItems } from "./nav";
import { CurrentProjectChip } from "../components/CurrentProjectChip";
import { ConnectionPill } from "../components/ConnectionPill";
import { ThemeToggle } from "../components/ThemeToggle";
import { SidebarToggle } from "../components/SidebarToggle";
import { subscribeSidebar, getSnapshot } from "./sidebar";

export function Layout() {
  const snap = useSyncExternalStore(subscribeSidebar, getSnapshot, () => "false");
  const collapsed = snap === "true";
  return (
    <div className={styles.shell} data-collapsed={String(collapsed)}>
      <aside className={styles.sidebar}>
        <div className={styles.sidebarHeader}>
          {!collapsed && <div className={styles.brand}>Cookbook scanner</div>}
          <SidebarToggle />
        </div>
        <nav id="primary-navigation" aria-label="Primary">
          <ul className={styles.navList}>
            {navItems.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  className={styles.navLink}
                  data-testid={item.testid}
                  aria-label={collapsed ? item.label : undefined}
                  title={collapsed ? item.label : undefined}
                >
                  {({ isActive }) => (
                    <>
                      <item.icon
                        className={styles.icon}
                        size={16}
                        strokeWidth={1.75}
                        aria-hidden
                        focusable="false"
                      />
                      <span
                        className={styles.label}
                        data-active={isActive ? "true" : "false"}
                      >
                        {item.label}
                      </span>
                    </>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </aside>
      <div className={styles.main}>
        <header className={styles.topbar}>
          <div className={styles.topbarLeft}>
            <CurrentProjectChip />
          </div>
          <div className={styles.topbarRight}>
            <ThemeToggle />
            <ConnectionPill />
          </div>
        </header>
        <main className={styles.content}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
