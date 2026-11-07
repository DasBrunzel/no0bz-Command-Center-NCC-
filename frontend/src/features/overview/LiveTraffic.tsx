import { useEffect, useSyncExternalStore } from "react";
import type { FleetNode } from "../../api/types";
import { LineChart } from "../../components/charts";
import { Empty, Reading } from "../../components/ui";
import { fmt1, fmtTime } from "../../lib/format";
import { down, up } from "../../lib/node";
import { Link } from "../../lib/router";

/*
 * There is no fleet-wide traffic endpoint, so the sum of every online node's
 * latest network reading is sampled on each nodes poll and kept in memory
 * for the session (see DECISIONS.md, API proposals).
 */
interface Sample { at: number; down: number; up: number }
const MAX = 90;
let samples: Sample[] = [];
let lastStamp = 0;
const listeners = new Set<() => void>();

function record(nodes: FleetNode[], stamp: number): void {
  if (!stamp || stamp === lastStamp) return;
  lastStamp = stamp;
  const online = nodes.filter((node) => node.online);
  const sample = {
    at: stamp,
    down: online.reduce((sum, node) => sum + (down(node.latest?.metrics) ?? 0), 0),
    up: online.reduce((sum, node) => sum + (up(node.latest?.metrics) ?? 0), 0),
  };
  samples = [...samples.slice(-(MAX - 1)), sample];
  for (const listener of listeners) listener();
}

function useSamples(): Sample[] {
  return useSyncExternalStore(
    (listener) => { listeners.add(listener); return () => listeners.delete(listener); },
    () => samples,
  );
}

export function LiveTraffic({ nodes, updatedAt }: { nodes: FleetNode[]; updatedAt: number }) {
  useEffect(() => record(nodes, updatedAt), [nodes, updatedAt]);
  const history = useSamples();
  const current = history[history.length - 1];
  const talkers = nodes
    .filter((node) => node.online && ((down(node.latest?.metrics) ?? 0) + (up(node.latest?.metrics) ?? 0)) > 0)
    .sort((a, b) => (down(b.latest?.metrics) ?? 0) + (up(b.latest?.metrics) ?? 0) - (down(a.latest?.metrics) ?? 0) - (up(a.latest?.metrics) ?? 0))
    .slice(0, 5);

  return (
    <section className="panel live-traffic" aria-labelledby="traffic-title">
      <div className="panel-head">
        <h2 id="traffic-title">Live-Verkehr</h2>
        <p>Summe aller Geräte, die gerade online sind</p>
      </div>
      <div className="traffic-now">
        <div><span className="ink-3 small">Download</span><Reading value={current?.down ?? null} unit="Mbit/s" digits={1} /></div>
        <div><span className="ink-3 small">Upload</span><Reading value={current?.up ?? null} unit="Mbit/s" digits={1} /></div>
      </div>
      {history.length < 3 ? (
        <p className="ink-3 small traffic-wait">Der Verlauf sammelt sich, solange diese Seite offen ist – ein Messpunkt alle paar Sekunden.</p>
      ) : (
        <LineChart
          title="Live-Verkehr der Fleet in Mbit/s"
          unit="Mbit/s"
          height={160}
          format={(value) => fmt1(value)}
          labels={history.map((sample) => fmtTime(new Date(sample.at)))}
          series={[
            { name: "Download", color: "var(--c-series-1)", values: history.map((sample) => sample.down) },
            { name: "Upload", color: "var(--c-series-2)", values: history.map((sample) => sample.up) },
          ]}
        />
      )}
      {talkers.length > 0 ? (
        <table className="table mt-4">
          <caption className="visually-hidden">Geräte mit dem meisten Verkehr</caption>
          <thead><tr><th>Gerät</th><th className="r">Download</th><th className="r">Upload</th></tr></thead>
          <tbody>
            {talkers.map((node) => (
              <tr key={node.node_id}>
                <td><Link to={`geraete/${encodeURIComponent(node.node_id)}`}>{node.display_name}</Link></td>
                <td className="r"><Reading value={down(node.latest?.metrics)} unit="Mbit/s" digits={1} /></td>
                <td className="r"><Reading value={up(node.latest?.metrics)} unit="Mbit/s" digits={1} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="mt-4"><Empty title="Gerade Funkstille" icon="network">Kein Gerät überträgt im Moment nennenswert Daten.</Empty></div>
      )}
    </section>
  );
}
