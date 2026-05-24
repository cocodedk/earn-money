import type { AgentSession, BudgetSnapshot } from "./types";
import { isTerminalStatus } from "./types";
import { BudgetBars } from "./BudgetBars";
import styles from "./MissionStrip.module.css";

type Props = {
  session: AgentSession;
  budgetOverlay: BudgetSnapshot | null;
};

export function MissionStrip({ session, budgetOverlay }: Props) {
  const isTerminal = isTerminalStatus(session.status);
  return (
    <div className={styles.strip}>
      <div className={styles.row}>
        <div className={styles.identity}>
          <span className={styles.profile}>{session.mission_profile}</span>
          <span className={styles.host}>{session.target_host}</span>
          <span className={styles.statusPill} data-status={session.status}>
            {session.status}
          </span>
        </div>
        <div className={styles.phases} role="list" aria-label="Mission phases">
          {session.active_phases.map((phase, i) => (
            <span key={phase} role="listitem">
              {i > 0 && <span className={styles.arrow} aria-hidden="true">{"→"}</span>}
              <span
                className={styles.chip}
                data-testid={`phase-chip-${phase}`}
                data-current={phase === session.current_phase ? "true" : "false"}
                aria-current={phase === session.current_phase ? "step" : undefined}
              >
                {phase}
              </span>
            </span>
          ))}
        </div>
        <BudgetBars session={session} budgetOverlay={budgetOverlay} />
      </div>
      {isTerminal && (
        <p className={styles.reason}>{session.terminal_reason || "Mission ended."}</p>
      )}
    </div>
  );
}
