import { useState } from "react";
import { useHardwareStats, useNodes } from "../../api/queries";
import { DaysPicker, ErrorState, Loading, PageHead } from "../../components/ui";
import { sortByLayout } from "../../lib/node";
import type { Route } from "../../lib/router";
import { HardwareSummary } from "./HardwareSummary";

export default function Hardware(_: { route: Route }) {
  const [days, setDays] = useState(30);
  const [nodeId, setNodeId] = useState<string>("");
  const nodes = useNodes();
  const stats = useHardwareStats(days, nodeId || null);

  return (
    <div>
      <PageHead title="Hardware-Statistik" lead="Wie warm, wie laut, wie hungrig die Fleet war – stündlich gesammelt, für jede Maschine oder alle zusammen." />
      <div className="filters">
        <DaysPicker value={days} onChange={setDays} />
        <label className="field">
          <span className="visually-hidden">Gerät</span>
          <select className="select" value={nodeId} onChange={(event) => setNodeId(event.target.value)}>
            <option value="">Alle Geräte</option>
            {[...(nodes.data ?? [])].sort(sortByLayout).map((node) => <option key={node.node_id} value={node.node_id}>{node.display_name}</option>)}
          </select>
        </label>
      </div>
      {stats.isPending ? (
        <Loading label="Statistik wird geladen" />
      ) : stats.isError && !stats.data ? (
        <ErrorState onRetry={() => void stats.refetch()}>Die Hardware-Statistik konnte nicht geladen werden.</ErrorState>
      ) : (
        <section className="panel" data-refreshing={stats.isPlaceholderData || undefined} aria-labelledby="hw-period">
          <div className="panel-head">
            <h2 id="hw-period">{days ? `Letzte ${days} Tage` : "Gesamter Zeitraum"}</h2>
            <p>{nodeId ? nodes.data?.find((node) => node.node_id === nodeId)?.display_name : "alle Geräte"}</p>
          </div>
          <HardwareSummary stats={stats.data!} />
        </section>
      )}
    </div>
  );
}
