import { NavLink, Outlet } from "react-router-dom";
import styles from "./Layout.module.css";
import { navItems } from "./nav";
import { CurrentProjectChip } from "../components/CurrentProjectChip";
import { ConnectionPill } from "../components/ConnectionPill";
import { ThemeToggle } from "../components/ThemeToggle";

export function Layout() {
  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}>Cookbook scanner</div>
        <nav>
          <ul className={styles.navList}>
            {navItems.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  className={styles.navLink}
                  data-testid={item.testid}
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
