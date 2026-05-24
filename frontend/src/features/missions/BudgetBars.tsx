import type { AgentSession, BudgetSnapshot } from "./types";
import styles from "./BudgetBars.module.css";

type BarDef = { label: string; used: number; max: number };

const BUDGET_KEYS: { budget: string; counter: string; label: string }[] = [
  { budget: "max_turns", counter: "turns", label: "Turns" },
  { budget: "max_http_requests", counter: "http_requests", label: "HTTP" },
  { budget: "max_browser_actions", counter: "browser_actions", label: "Browser" },
  { budget: "max_llm_calls", counter: "llm_calls", label: "LLM" },
];

function usedValue(snap: BudgetSnapshot, key: string): number {
  const mission = snap.mission;
  if (mission && typeof mission[key] === "number") return mission[key]!;
  const direct = snap[key];
  return typeof direct === "number" ? direct : 0;
}

function buildBars(session: AgentSession, overlay: BudgetSnapshot | null): BarDef[] {
  const snap = overlay ?? session.consumed_budget;
  const bars: BarDef[] = [];
  for (const { budget, counter, label } of BUDGET_KEYS) {
    const max = session.mission_budget[budget];
    if (typeof max !== "number") continue;
    bars.push({ label, used: usedValue(snap, counter), max });
  }
  return bars;
}

function pct(used: number, max: number): number {
  if (max <= 0) return 0;
  return Math.min(100, Math.round((used / max) * 100));
}

type Props = { session: AgentSession; budgetOverlay: BudgetSnapshot | null };

export function BudgetBars({ session, budgetOverlay }: Props) {
  const bars = buildBars(session, budgetOverlay);
  if (bars.length === 0) {
    const snap = budgetOverlay ?? session.consumed_budget;
    const used = usedValue(snap, "turns");
    return <span className={styles.fallback}>{used} turns used</span>;
  }

  return (
    <div className={styles.bars} data-testid="budget-bars">
      {bars.map((bar) => (
        <div key={bar.label} className={styles.barGroup}>
          <span className={styles.barLabel}>
            {bar.label}: {bar.used}/{bar.max}
          </span>
          <div className={styles.track}>
            <div
              className={styles.fill}
              style={{ width: `${pct(bar.used, bar.max)}%` }}
              data-hot={pct(bar.used, bar.max) >= 80 ? "true" : undefined}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
