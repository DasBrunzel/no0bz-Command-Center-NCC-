import { useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { api, qk } from "../../api/endpoints";
import { useHardwareStats } from "../../api/queries";
import type { FleetNode, SensorRole } from "../../api/types";
import { useCan } from "../../app/auth";
import { Icon } from "../../components/Icon";
import { useToast } from "../../components/toast";
import { DaysPicker, Empty, Loading, Meter, Reading } from "../../components/ui";
import { num } from "../../lib/format";
import { HardwareSummary } from "../hardware/HardwareSummary";
import { Vendor } from "./OverviewTab";

const ROLES: Array<{ value: SensorRole; label: string }> = [
  { value: "cpu", label: "CPU-Lüfter" },
  { value: "case", label: "Gehäuselüfter" },
  { value: "gpu", label: "GPU" },
  { value: "pump", label: "Pumpe" },
  { value: "radiator", label: "Radiator" },
];

export default function SensorsTab({ node }: { node: FleetNode }) {
  const m = node.latest?.metrics;
  const [days, setDays] = useState(30);
  const stats = useHardwareStats(days, node.node_id);
  const hardware = m?.hardware;
  const modules = hardware?.memory_modules ?? [];
  const storage = hardware?.storage ?? [];
  const isWindows = node.platform.toLowerCase().startsWith("win");
  const missingDriver = isWindows && hardware?.provider === "librehardwaremonitor" && typeof hardware.pawnio === "string" && hardware.pawnio !== "running";

  return (
    <div className="stack">
      {!m ? (
        <Empty title="Keine Sensordaten" icon="hardware">Das Gerät hat noch keine Hardware-Werte geschickt.</Empty>
      ) : (
        <div className="sensor-grid">
          <section className="panel">
            <div className="panel-head"><h2>Prozessor</h2><Vendor name={m.cpu?.model} /></div>
            <p className="sensor-model">{m.cpu?.model ?? "Unbekannte CPU"}</p>
            <dl className="kv">
              <dt>Temperatur</dt><dd><Reading value={num(m.cpu?.temperature_c)} unit="°C" /></dd>
              <dt>Leistung</dt><dd><Reading value={num(m.cpu?.power_w)} unit="W" /></dd>
              <dt>Kerne / Threads</dt><dd>{m.cpu?.physical_cores ?? "–"} / {m.cpu?.logical_cores ?? "–"}</dd>
            </dl>
            {m.cpu?.per_core?.length ? (
              <div className="cores" aria-label="Auslastung je Kern">
                {m.cpu.per_core.map((value, index) => <Meter key={index} value={value} label={`Kern ${index + 1}`} />)}
              </div>
            ) : null}
          </section>
          {(m.gpus ?? []).map((gpu, index) => {
            const lhm = m.lhm_gpus?.[index];
            return (
              <section className="panel" key={index}>
                <div className="panel-head"><h2>Grafikkarte{(m.gpus?.length ?? 0) > 1 ? ` ${index + 1}` : ""}</h2><Vendor name={gpu.name} /></div>
                <p className="sensor-model">{gpu.name ?? lhm?.name ?? "Unbekannte GPU"}</p>
                <dl className="kv">
                  <dt>Temperatur</dt><dd><Reading value={num(lhm?.temperature_c) ?? num(gpu.temperature_c)} unit="°C" /></dd>
                  {num(lhm?.hotspot_temperature_c) != null && <><dt>Hotspot</dt><dd><Reading value={num(lhm?.hotspot_temperature_c)} unit="°C" /></dd></>}
                  {num(lhm?.memory_temperature_c) != null && <><dt>Speicher</dt><dd><Reading value={num(lhm?.memory_temperature_c)} unit="°C" /></dd></>}
                  <dt>Leistung</dt><dd><Reading value={num(lhm?.power_w) ?? num(gpu.power_w)} unit="W" /></dd>
                  <dt>Lüfter</dt><dd>{num(lhm?.fan_rpm) != null ? (lhm!.fan_rpm! > 0 ? <Reading value={lhm!.fan_rpm} unit="U/min" /> : "steht") : <Reading value={num(gpu.fan_percent)} unit="%" />}</dd>
                  <dt>VRAM</dt><dd><Reading value={num(gpu.vram_percent)} unit="%" /></dd>
                </dl>
              </section>
            );
          })}
          <section className="panel">
            <div className="panel-head"><h2>Speicher & Laufwerke</h2></div>
            {modules.length === 0 && storage.length === 0 ? (
              <p className="ink-3 small">Keine Temperaturen für RAM oder Laufwerke gemeldet.</p>
            ) : (
              <dl className="kv">
                {modules.map((item, index) => <Pair key={`m${index}`} label={item.name ?? item.slot ?? `Modul ${index + 1}`} value={<Reading value={num(item.temperature_c)} unit="°C" />} />)}
                {storage.map((item, index) => <Pair key={`s${index}`} label={item.name ?? `Laufwerk ${index + 1}`} value={<Reading value={num(item.temperature_c)} unit="°C" />} />)}
              </dl>
            )}
          </section>
          <Mainboard node={node} missingDriver={missingDriver} />
        </div>
      )}

      <section className="panel" aria-labelledby="hwstats-title">
        <div className="panel-head">
          <h2 id="hwstats-title">Hardware-Statistik</h2>
          <DaysPicker value={days} onChange={setDays} />
        </div>
        {stats.isPending ? <Loading /> : stats.data ? <div data-refreshing={stats.isPlaceholderData || undefined}><HardwareSummary stats={stats.data} /></div> : <p className="ink-3 small">Statistik nicht verfügbar.</p>}
      </section>
    </div>
  );
}

function Pair({ label, value }: { label: string; value: ReactNode }) {
  return <><dt>{label}</dt><dd>{value}</dd></>;
}

function Mainboard({ node, missingDriver }: { node: FleetNode; missingDriver: boolean }) {
  const can = useCan();
  const board = node.latest?.metrics.hardware?.board;
  const boardName = typeof node.latest?.metrics.hardware?.components?.board === "string" ? node.latest.metrics.hardware.components.board : null;
  const fans = board?.fans ?? [];
  const temperatures = board?.temperatures ?? [];
  const fastest = Math.max(1, ...fans.map((fan) => fan.rpm ?? 0));
  const editable = can.manage(node);

  return (
    <section className="panel mainboard">
      <div className="panel-head">
        <h2>Mainboard</h2>
        <p>{boardName ?? board?.chip ?? "Unbekannt"}</p>
      </div>
      {missingDriver && (
        <div className="state state-compact" data-kind="error">
          <h3>CPU- und Mainboard-Sensoren fehlen</h3>
          <p>Unter Windows braucht LibreHardwareMonitor den signierten Treiber PawnIO. Einmal als Administrator installieren, dann erscheinen Lüfter und Temperaturen.</p>
        </div>
      )}
      {fans.length > 0 && (
        <>
          <h3 className="chart-title">Lüfter</h3>
          <ul className="plain sensor-list" role="list">
            {fans.map((fan) => (
              <SensorRow key={fan.label} node={node} sensorKey={`fan:${fan.label}`} fallback={fan.label} editable={editable} withRole>
                <Meter value={((fan.rpm ?? 0) / fastest) * 100} label={`${fan.label} relativ`} caution={101} stop={101} />
                <span className="num">{fan.rpm ? <Reading value={fan.rpm} unit="U/min" /> : <span className="ink-3">steht</span>}</span>
              </SensorRow>
            ))}
          </ul>
        </>
      )}
      {temperatures.length > 0 && (
        <>
          <h3 className="chart-title mt-4">Temperaturfühler</h3>
          <ul className="plain sensor-list" role="list">
            {temperatures.map((sensor) => (
              <SensorRow key={sensor.label} node={node} sensorKey={`temp:${sensor.label}`} fallback={sensor.label} editable={editable}>
                <span />
                <span className="num"><Reading value={num(sensor.value)} unit="°C" /></span>
              </SensorRow>
            ))}
          </ul>
          <p className="form-hint mt-4">Welcher Fühler zu welchem Anschluss gehört, hängt vom Mainboard ab. Unbelegte Eingänge zeigen oft unrealistische Werte.</p>
        </>
      )}
      {!fans.length && !temperatures.length && !missingDriver && <p className="ink-3 small">Keine Mainboard-Sensoren gemeldet.</p>}
      {(fans.length > 0 || temperatures.length > 0) && !editable && <p className="form-hint mt-4">Namen vergeben dürfen Commander und der Besitzer des Geräts.</p>}
    </section>
  );
}

function SensorRow({ node, sensorKey, fallback, editable, withRole, children }: {
  node: FleetNode; sensorKey: string; fallback: string; editable: boolean; withRole?: boolean; children: ReactNode;
}) {
  const label = node.sensor_labels[sensorKey];
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(label?.name ?? "");
  const [role, setRole] = useState<SensorRole | "">(label?.role ?? "");
  const [busy, setBusy] = useState(false);
  const client = useQueryClient();
  const toast = useToast();

  const save = async () => {
    setBusy(true);
    try {
      const updated = await api.fleet.setSensorLabel(node.node_id, sensorKey, name.trim() || null, role || null);
      client.setQueryData(qk.node(node.node_id), updated);
      await client.invalidateQueries({ queryKey: qk.nodes });
      setEditing(false);
      toast.ok(name.trim() || role ? "Sensor benannt." : "Name entfernt.");
    } catch (error) {
      toast.fail(error, "Der Name konnte nicht gespeichert werden.");
    } finally {
      setBusy(false);
    }
  };

  if (editing) {
    return (
      <li className="sensor-row editing">
        <form className="sensor-form" onSubmit={(event) => { event.preventDefault(); void save(); }}>
          <label className="field"><span>Name für „{fallback}“</span><input className="input" maxLength={48} value={name} onChange={(event) => setName(event.target.value)} placeholder={fallback} autoFocus /></label>
          {withRole && (
            <label className="field"><span>Rolle</span>
              <select className="select" value={role} onChange={(event) => setRole(event.target.value as SensorRole | "")}>
                <option value="">keine</option>
                {ROLES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
            </label>
          )}
          <div className="actions">
            <button type="submit" className="btn btn-primary btn-s" disabled={busy}>Speichern</button>
            <button type="button" className="btn btn-s" onClick={() => setEditing(false)}>Abbrechen</button>
          </div>
        </form>
      </li>
    );
  }
  const roleLabel = ROLES.find((item) => item.value === label?.role)?.label;
  return (
    <li className="sensor-row">
      <span className="sensor-name">
        <b>{label?.name || fallback}</b>
        {(label?.name || roleLabel) && <small>{label?.name ? fallback : ""}{label?.name && roleLabel ? " · " : ""}{roleLabel ?? ""}</small>}
      </span>
      {children}
      {editable && (
        <button type="button" className="btn btn-quiet btn-icon btn-s" onClick={() => setEditing(true)} aria-label={`${label?.name || fallback} benennen`} title="Benennen">
          <Icon name="edit" />
        </button>
      )}
    </li>
  );
}
