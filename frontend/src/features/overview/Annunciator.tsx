import { useState } from "react";
import { api, qk } from "../../api/endpoints";
import { useAction } from "../../api/queries";
import type { FleetAlert } from "../../api/types";
import { useCan } from "../../app/auth";
import { Icon } from "../../components/Icon";
import { useToast } from "../../components/toast";
import { ConfirmDialog, ErrorState, Lamp, Loading, RelTime } from "../../components/ui";
import { plural } from "../../lib/format";
import { Link } from "../../lib/router";

const KIND: Record<string, string> = {
  cpu: "CPU-Last", memory: "Arbeitsspeicher", gpu: "GPU-Last", disk: "Speicherplatz", offline: "Offline",
  cpu_temperature: "CPU-Temperatur", gpu_temperature: "GPU-Temperatur", drive_temperature: "Laufwerkstemperatur",
};

/** The fault annunciator: every active alert is a lit window. */
export function Annunciator({ alerts, loading, error, onRetry }: { alerts: FleetAlert[]; loading: boolean; error: boolean; onRetry: () => void }) {
  const can = useCan();
  const toast = useToast();
  const [confirm, setConfirm] = useState(false);
  const clear = useAction(() => api.fleet.clearAlerts(), [qk.alerts, qk.summary]);
  const active = alerts.filter((alert) => alert.active);
  const resolved = alerts.filter((alert) => !alert.active).slice(0, 6);

  return (
    <section className="panel annunciator" aria-labelledby="alerts-title">
      <div className="panel-head">
        <h2 id="alerts-title">Störmelder</h2>
        {can.commander && active.length > 0 && (
          <button type="button" className="btn btn-s" onClick={() => setConfirm(true)}>
            <Icon name="check" /> Alle quittieren
          </button>
        )}
      </div>
      {loading ? (
        <Loading label="Warnungen werden geladen" />
      ) : error ? (
        <ErrorState onRetry={onRetry}>Die Warnungen konnten nicht abgefragt werden.</ErrorState>
      ) : active.length === 0 ? (
        <div className="annunciator-calm">
          <Lamp state="go" />
          <p><b>Keine Störung.</b> Kein Gerät überschreitet gerade eine Warnregel.</p>
        </div>
      ) : (
        <ul className="annunciator-grid plain" role="list">
          {active.map((alert) => (
            <li key={alert.alert_id} className="annunciator-window" data-severity={alert.severity}>
              <Lamp state={alert.severity === "critical" ? "stop" : "caution"} blink={alert.severity === "critical"} label={alert.severity === "critical" ? "Kritisch" : "Warnung"} />
              <div>
                <Link to={`geraete/${encodeURIComponent(alert.node_id)}`} className="annunciator-node">{alert.display_name}</Link>
                <p>{alert.message}</p>
                <small>{KIND[alert.kind] ?? alert.kind} · seit <RelTime iso={alert.opened_at} /></small>
              </div>
            </li>
          ))}
        </ul>
      )}
      {resolved.length > 0 && (
        <details className="annunciator-history">
          <summary>Zuletzt erledigt ({resolved.length})</summary>
          <ul className="plain" role="list">
            {resolved.map((alert) => (
              <li key={alert.alert_id}>
                <Lamp state="off" size="s" />
                <span><b>{alert.display_name}</b> – {alert.message}</span>
                <small className="ink-3"><RelTime iso={alert.resolved_at ?? alert.updated_at} /></small>
              </li>
            ))}
          </ul>
        </details>
      )}
      <ConfirmDialog
        open={confirm}
        onClose={() => setConfirm(false)}
        title="Alle Warnungen quittieren?"
        confirmLabel="Quittieren"
        busy={clear.isPending}
        onConfirm={() =>
          clear.mutate(undefined, {
            onSuccess: (result) => { toast.ok(`${plural(result.cleared, "Warnung", "Warnungen")} quittiert.`); setConfirm(false); },
            onError: (failure) => toast.fail(failure),
          })
        }
      >
        <p>{plural(active.length, "aktive Warnung wird", "aktive Warnungen werden")} geschlossen. Besteht die Ursache weiter, meldet NCC sie beim nächsten Messwert erneut.</p>
      </ConfirmDialog>
    </section>
  );
}
