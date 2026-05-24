import type { AgentAction } from "./types";
import styles from "./OutcomeDigest.module.css";

const SKIP_ACTIONS = new Set(["store_note", "stop", "request_phase_transition"]);

type ObsData = Record<string, unknown>;

function getUrl(data: ObsData): string | null {
  const url = data.url ?? data.current_url;
  return typeof url === "string" ? url : null;
}

function getTitle(data: ObsData): string | null {
  const title = data.title ?? data.page_title;
  return typeof title === "string" ? title : null;
}

type Counters = { routes: number; assets: number; elements: number; network: number };

function countDiscoveries(data: ObsData): Counters {
  const disc = data.discovered as Record<string, unknown[]> | undefined;
  const routes = Array.isArray(disc?.routes) ? disc.routes.length : 0;
  const assets = Array.isArray(disc?.assets) ? disc.assets.length : 0;
  const elems = data.elements as Record<string, unknown> | undefined;
  const elements =
    (typeof elems?.links === "number" ? elems.links : 0) +
    (typeof elems?.buttons === "number" ? elems.buttons : 0) +
    (typeof elems?.forms === "number" ? elems.forms : 0);
  const net = data.network as unknown[] | undefined;
  const network = Array.isArray(net) ? net.length : 0;
  return { routes, assets, elements, network };
}

function summaryFromData(data: ObsData): Counters {
  return countDiscoveries(data);
}

type Props = { action: AgentAction };

export function OutcomeDigest({ action }: Props) {
  if (SKIP_ACTIONS.has(action.action_type)) return null;
  const obs = action.observations;
  if (obs.length === 0) return null;

  const first = obs[0];
  const data = first.data;
  const summary = (data.observation_summary as string) ?? null;
  const url = getUrl(data);
  const title = getTitle(data);
  const counts = summary ? null : summaryFromData(data);
  const hasCounters = counts && (counts.routes + counts.assets + counts.elements + counts.network > 0);

  if (!url && !title && !summary && !hasCounters) return null;

  return (
    <div className={styles.digest} data-testid="outcome-digest">
      <span className={styles.label}>Observed:</span>
      {url && <span className={styles.url}>{url}</span>}
      {title && <span className={styles.title}>{title}</span>}
      {summary && <span className={styles.summary}>{summary}</span>}
      {hasCounters && (
        <span className={styles.counters}>
          {counts.routes > 0 && <span>{counts.routes} routes</span>}
          {counts.assets > 0 && <span>{counts.assets} assets</span>}
          {counts.elements > 0 && <span>{counts.elements} elements</span>}
          {counts.network > 0 && <span>{counts.network} requests</span>}
        </span>
      )}
    </div>
  );
}
