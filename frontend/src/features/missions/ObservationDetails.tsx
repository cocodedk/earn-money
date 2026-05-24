import { useState } from "react";
import type { AgentObservation } from "./types";
import styles from "./ObservationDetails.module.css";

type ObsData = Record<string, unknown>;

function getStr(data: ObsData, ...keys: string[]): string | null {
  for (const k of keys) {
    if (typeof data[k] === "string") return data[k] as string;
  }
  return null;
}

function getArray(data: ObsData, path: string): unknown[] {
  const parts = path.split(".");
  let cur: unknown = data;
  for (const p of parts) {
    if (cur && typeof cur === "object") cur = (cur as Record<string, unknown>)[p];
    else return [];
  }
  return Array.isArray(cur) ? cur : [];
}

type NetworkRow = { url: string; status: number; method: string };

function extractNetwork(data: ObsData): NetworkRow[] {
  const raw = getArray(data, "network");
  return raw
    .filter((r): r is Record<string, unknown> => typeof r === "object" && r !== null)
    .map((r) => ({
      url: String(r.url ?? ""),
      status: typeof r.status === "number" ? r.status : 0,
      method: typeof r.method === "string" ? r.method : "GET",
    }))
    .slice(0, 20);
}

type ElementCounts = { links: number; buttons: number; forms: number };

function extractElements(data: ObsData): ElementCounts | null {
  const elems = data.elements;
  if (!elems || typeof elems !== "object") return null;
  const e = elems as Record<string, unknown>;
  const links = typeof e.links === "number" ? e.links : 0;
  const buttons = typeof e.buttons === "number" ? e.buttons : 0;
  const forms = typeof e.forms === "number" ? e.forms : 0;
  if (links + buttons + forms === 0) return null;
  return { links, buttons, forms };
}

type Props = { observations: AgentObservation[] };

export function ObservationDetails({ observations }: Props) {
  const [rawOpen, setRawOpen] = useState(false);
  if (observations.length === 0) return null;

  const first = observations[0];
  const data = first.data;
  const url = getStr(data, "url", "current_url");
  const title = getStr(data, "title", "page_title");
  const routes = getArray(data, "discovered.routes").map(String);
  const assets = getArray(data, "discovered.assets").map(String);
  const network = extractNetwork(data);
  const elements = extractElements(data);
  const hasStructured = url || title || routes.length || assets.length || network.length || elements;

  return (
    <div className={styles.obsDetails} data-testid="observation-details">
      {hasStructured && (
        <>
          {(url || title) && (
            <div className={styles.section}>
              <span className={styles.heading}>Page</span>
              {url && <div className={styles.mono}>{url}</div>}
              {title && <div>{title}</div>}
            </div>
          )}
          {routes.length > 0 && (
            <div className={styles.section}>
              <span className={styles.heading}>Routes ({routes.length})</span>
              <ul className={styles.list}>
                {routes.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </div>
          )}
          {assets.length > 0 && (
            <div className={styles.section}>
              <span className={styles.heading}>Assets ({assets.length})</span>
              <ul className={styles.list}>
                {assets.map((a, i) => <li key={i}>{a}</li>)}
              </ul>
            </div>
          )}
          {network.length > 0 && (
            <div className={styles.section}>
              <span className={styles.heading}>Network ({network.length})</span>
              <table className={styles.netTable}>
                <thead>
                  <tr><th>Method</th><th>Status</th><th>URL</th></tr>
                </thead>
                <tbody>
                  {network.map((n, i) => (
                    <tr key={i}>
                      <td>{n.method}</td>
                      <td>{n.status || "—"}</td>
                      <td className={styles.urlCell}>{n.url}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {elements && (
            <div className={styles.section}>
              <span className={styles.heading}>Elements</span>
              <span className={styles.elCounts}>
                {elements.links} links, {elements.buttons} buttons, {elements.forms} forms
              </span>
            </div>
          )}
        </>
      )}
      <details open={rawOpen} onToggle={(e) => setRawOpen((e.target as HTMLDetailsElement).open)}>
        <summary className={styles.rawToggle}>Raw JSON</summary>
        <pre className={styles.rawPre}>
          {JSON.stringify(observations.map((o) => ({
            type: o.observation_type, data: o.data,
          })), null, 2)}
        </pre>
      </details>
    </div>
  );
}
