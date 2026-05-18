import { NavLink, Outlet } from "react-router-dom";
import styles from "./Layout.module.css";
import { navItems } from "./nav";

export function Layout() {
  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}>Cookbook scanner</div>
        <nav>
          <ul className={styles.navList}>
            {navItems.map((item) => (
              <li key={item.to}>
                <NavLink to={item.to} className={styles.navLink} end>
                  {({ isActive }) => (
                    <span data-active={isActive ? "true" : "false"}>
                      {item.label}
                    </span>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </aside>
      <div className={styles.main}>
        <header className={styles.topbar}>
          <div className={styles.topbarLeft}>{/* current project chip slot (Task V) */}</div>
          <div className={styles.topbarRight}>{/* connection pill slot (Task Q) */}</div>
        </header>
        <main className={styles.content}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
