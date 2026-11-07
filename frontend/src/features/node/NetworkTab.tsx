import { useState } from "react";
import { api } from "../../api/endpoints";
import { useAction, useNetworkHistory, useNetworkMonth } from "../../api/queries";
import type { FleetNode } from "../../api/types";
import { useCan } from "../../app/auth";
import { LineChart } from "../../components/charts";
import { Icon } from "../../components/Icon";
import { useToast } from "../../components/toast";
import { ConfirmDialog, Empty, ErrorState, Loading, Reading } from "../../components/ui";
import { fmt1, fmtBytes, fmtDate, fmtTime, num } from "../../lib/format";

export default function NetworkTab({ node }: { node: FleetNode }) {
  const can = useCan();
  const toast = useToast();
  const history = useNetworkHistory(node.node_id, 120);
  const month = useNetworkMonth(node.node_id);
  const [confirm, setConfirm] = useState(false);
  const reset = useAction(() => api.fleet.resetNetwork(), [["fleet", "network-month"], ["fleet", "network-history"]]);
  const net = node.online ? node.latest?.metrics.network : null;
  const samples = (history.data ?? []).filter((sample) => sample.network);

  return (
    <div className="stack">
      <div className="net-now">
        <div className="gauge">
          <header><h2>Jetzt</h2></header>
          <p className="gauge-value gauge-net"><span>↓</span><Reading value={num(net?.download_mbps)} unit="Mbit/s" digits={1} /></p>
          <p className="gauge-value gauge-net"><span>↑</span><Reading value={num(net?.upload_mbps)} unit="Mbit/s" digits={1} /></p>
          <p className="gauge-model">{node.online ? net?.interface ?? "Schnittstelle unbekannt" : "Gerät offline"}</p>
        </div>
        <section className="gauge">
          <header><h2>Dieser Monat</h2></header>
          {month.isPending ? <Loading /> : month.isError ? (
            <p className="ink-3 small">Monatsverbrauch nicht abrufbar.</p>
          ) : !month.data!.available ? (
            <p className="ink-3 small">Noch keine Zählerstände für diesen Monat.</p>
          ) : (
            <>
              <p className="gauge-value gauge-net"><span>↓</span>{fmtBytes(month.data!.received_bytes)}</p>
              <p className="gauge-value gauge-net"><span>↑</span>{fmtBytes(month.data!.sent_bytes)}</p>
              <p className="gauge-model">seit {fmtDate(month.data!.period_start)} · {month.data!.samples.toLocaleString("de-DE")} Messungen</p>
            </>
          )}
        </section>
      </div>

      <section className="panel" aria-labelledby="net-history">
        <div className="panel-head">
          <h2 id="net-history">Verlauf</h2>
          <p>aktualisiert alle 30 Sekunden</p>
        </div>
        {history.isPending ? <Loading /> : history.isError && !history.data ? (
          <ErrorState onRetry={() => void history.refetch()}>Die Netzwerk-Historie konnte nicht geladen werden.</ErrorState>
        ) : samples.length < 2 ? (
          <Empty title="Noch kein Verlauf" icon="network">Sobald der Agent Netzwerkwerte schickt, entsteht hier die Kurve.</Empty>
        ) : (
          <LineChart
            title="Netzwerkverkehr in Mbit/s"
            unit="Mbit/s"
            height={200}
            format={(value) => fmt1(value)}
            labels={samples.map((sample) => fmtTime(sample.recorded_at))}
            series={[
              { name: "Download", color: "var(--c-series-1)", values: samples.map((sample) => num(sample.network?.download_mbps)) },
              { name: "Upload", color: "var(--c-series-2)", values: samples.map((sample) => num(sample.network?.upload_mbps)) },
            ]}
          />
        )}
      </section>

      {can.commander && (
        <section className="panel danger-zone">
          <div className="panel-head"><h2>Zähler zurücksetzen</h2></div>
          <p className="small">Setzt die Netzwerkstatistik <b>aller Geräte</b> zurück – der Monatsverbrauch beginnt wieder bei null. Rohdaten bleiben erhalten.</p>
          <div className="actions mt-4">
            <button type="button" className="btn btn-danger" onClick={() => setConfirm(true)}><Icon name="refresh" /> Netzwerkzähler zurücksetzen</button>
          </div>
        </section>
      )}
      <ConfirmDialog
        open={confirm}
        onClose={() => setConfirm(false)}
        danger
        title="Netzwerkzähler für alle Geräte zurücksetzen?"
        confirmLabel="Zurücksetzen"
        busy={reset.isPending}
        onConfirm={() => reset.mutate(undefined, {
          onSuccess: () => { toast.ok("Netzwerkzähler zurückgesetzt."); setConfirm(false); },
          onError: (error) => toast.fail(error),
        })}
      >
        <p>Der Monatsverbrauch aller Geräte startet neu. Das lässt sich nicht rückgängig machen.</p>
      </ConfirmDialog>
    </div>
  );
}

