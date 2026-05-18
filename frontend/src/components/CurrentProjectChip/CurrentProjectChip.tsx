import { Link } from "react-router-dom";
import styles from "./CurrentProjectChip.module.css";
import { useCurrentProject } from "../../lib/useCurrentProject";

export function CurrentProjectChip() {
  const { project } = useCurrentProject();
  return (
    <div className={styles.chip} data-testid="current-project-chip">
      <span>{project ? project.name : "(no project selected)"}</span>
      <Link
        to="/projects"
        data-testid="current-project-switch"
        className={styles.switch}
      >
        switch
      </Link>
    </div>
  );
}
