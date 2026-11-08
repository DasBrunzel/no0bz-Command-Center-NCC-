import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type CSSProperties, type FormEvent } from "react";
import { api, qk } from "../../api/endpoints";
import type { AlertPolicy } from "../../api/types";
import { useCan } from "../../app/auth";
import { useToast } from "../../components/toast";
import { ErrorState, Loading } from "../../components/ui";

type ThresholdKey = { [K in keyof AlertPolicy]: AlertPolicy[K] extends number ? K : never }[keyof AlertPolicy];

const LOAD: Array<{ key: ThresholdKey; label: string }> = [
  { key: "cpu_threshold", label: "CPU-Last" },
  { key: "memory_threshold", label: "Arbeitsspeicher" },
  { key: "gpu_threshold", label: "GPU-Last" },
  { key: "disk_threshold", label: "Laufwerk belegt" },
];
const HEAT: Array<{ key: ThresholdKey; label: string }> = [
  { key: "cpu_temperature_threshold", label: "CPU" },
  { key: "gpu_temperature_threshold", label: "GPU" },
  { key: "drive_temperature_threshold", label: "Laufwerke" },
];

export default function AlertPolicyTab() {
  const can = useCan();
  const client = useQueryClient();
  const toast = useToast();
  const policy = useQuery({ queryKey: qk.alertPolicy, queryFn: api.fleet.alertPolicy });
  const [draft, setDraft] = useState<AlertPolicy | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (policy.data && !draft) setDraft(policy.data); }, [policy.data, draft]);

  if (policy.isPending || !draft) return policy.isError ? <ErrorState onRetry={() => void policy.refetch()}>Die Warnregeln konnten nicht geladen werden.</ErrorState> : <Loading />;
  const dirty = JSON.stringify(draft) !== JSON.stringify(policy.data);

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      const saved = await api.fleet.saveAlertPolicy(draft);
      client.setQueryData(qk.alertPolicy, saved);
      setDraft(saved);
      toast.ok("Warnregeln gespeichert. Sie gelten ab der nächsten Prüfung (alle 30 Sekunden).");
    } catch (error) {
      toast.fail(error);
    } finally {
      setBusy(false);
    }
  };

  const slider = (key: ThresholdKey, label: string, min: number, max: number, unit: string) => (
    <label className="threshold" key={key}>
      <span className="threshold-label">{label}</span>
      <input
        type="range"
        min={min}
        max={max}
        value={draft[key]}
        disabled={!can.commander}
        style={{ "--fill": `${((draft[key] - min) / (max - min)) * 100}%` } as CSSProperties}
        onChange={(event) => setDraft({ ...draft, [key]: Number(event.target.value) })}
        aria-valuetext={`${draft[key]} ${unit}`}
      />
      <output className="threshold-value num">{draft[key]}<span className="unit">{unit}</span></output>
    </label>
  );

  return (
    <form className="settings-grid" onSubmit={(event) => void save(event)}>
      <section className="panel">
        <div className="panel-head"><h2>Last</h2><p>Warnung ab dem Wert, kritisch ab +5 %</p></div>
        <div className="stack">{LOAD.map((item) => slider(item.key, item.label, 50, 100, "%"))}</div>
        <p className="form-hint mt-4">Im Gaming Mode schweigen CPU- und GPU-Last-Warnungen.</p>
      </section>
      <section className="panel">
        <div className="panel-head"><h2>Temperatur</h2><p>meldet auch im Gaming Mode</p></div>
        <div className="stack">{HEAT.map((item) => slider(item.key, item.label, 40, 110, "°C"))}</div>
      </section>
      <section className="panel">
        <div className="panel-head"><h2>Handy-App</h2><p>zusätzlich zu Telegram</p></div>
        <label className="switch">
          <input
            type="checkbox"
            checked={draft.app_alerts_enabled}
            disabled={!can.commander}
            onChange={(event) => setDraft({ ...draft, app_alerts_enabled: event.target.checked })}
          />
          Warnungen an gekoppelte NCC-Apps senden
        </label>
        <p className="form-hint mt-4">Die App muss verbunden sein und Warnungen in ihren Einstellungen erlauben. Commander-Handys bekommen alle Warnungen, andere nur die ihrer eigenen Geräte.</p>
      </section>
      <div className="actions settings-save">
        {can.commander ? (
          <>
            <button type="submit" className="btn btn-primary" disabled={busy || !dirty}>Warnregeln speichern</button>
            <button type="button" className="btn" disabled={!dirty} onClick={() => setDraft(policy.data!)}>Verwerfen</button>
          </>
        ) : (
          <span className="badge">nur Commander ändern Warnregeln</span>
        )}
      </div>
    </form>
  );
}
