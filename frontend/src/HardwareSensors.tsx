import React, { useState } from "react";
import { Meter as ConceptMeter, Sparkline as ConceptSparkline } from "./concept/components";
import { VendorLogo } from "./Vendor";

type Metrics = Record<string, any>;
export type SensorRole = "cpu" | "case" | "gpu" | "pump" | "radiator";
export type SensorLabels = Record<string, { name: string | null; role: SensorRole | null }>;

const PAWNIO_COMMAND = "winget install --id namazso.PawnIO -e";
const ROLES: { value: SensorRole; label: string }[] = [
  { value: "cpu", label: "CPU-Lüfter" },
  { value: "case", label: "Gehäuse" },
  { value: "radiator", label: "Radiator" },
  { value: "pump", label: "Pumpe" },
  { value: "gpu", label: "Grafikkarte" },
];
const ROLE_LABEL = Object.fromEntries(ROLES.map((role) => [role.value, role.label])) as Record<SensorRole, string>;

const isNumber = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const reading = (value: unknown, unit: string, digits = 0) => (isNumber(value) ? `${value.toFixed(digits)} ${unit}` : "—");
const rate = (mib: unknown) => {
  // The agent reports MiB/s; small values would otherwise all show as 0.0.
  const value = isNumber(mib) ? mib : 0;
  if (value >= 100) return `${value.toFixed(0)} MB/s`;
  if (value >= 1) return `${value.toFixed(1)} MB/s`;
  return `${Math.round(value * 1024)} KB/s`;
};
// LHM names unlabeled mainboard inputs "Fan #2"; which header that is depends
// on the board, so the user can give each one a name.
const defaultName = (label: string) => label.replace(/^Temperature #/, "Sensor ").replace(/^Fan #/, "Lüfter ");

function Item({ label, value, title }: { label: React.ReactNode; value: string; title?: string }) {
  return <div title={title}><span>{label}</span><b>{value}</b></div>;
}

function boardOf(metrics: Metrics) {
  const hardware = metrics.hardware || {};
  const board = hardware.board && typeof hardware.board === "object" ? hardware.board : {};
  return {
    fans: (Array.isArray(board.fans) ? board.fans : []) as Metrics[],
    temperatures: (Array.isArray(board.temperatures) ? board.temperatures : []) as Metrics[],
    chip: typeof board.chip === "string" ? board.chip : null,
  };
}

export function fanWithRole(metrics: Metrics, labels: SensorLabels, role: SensorRole) {
  const fan = boardOf(metrics).fans.find((item) => labels[`fan:${item.label}`]?.role === role);
  return fan ? { name: labels[`fan:${fan.label}`]?.name || ROLE_LABEL[role], rpm: fan.rpm as number } : null;
}

export function CpuCard({ metrics, series, labels }: { metrics: Metrics; series: number[]; labels: SensorLabels }) {
  const cpu = metrics.cpu || {};
  const model = String(cpu.model || "CPU nicht erkannt");
  const fan = fanWithRole(metrics, labels, "cpu");
  return <div className="metric-card">
    <div className="metric-title"><span>CPU</span><VendorLogo name={model} size={26} /></div>
    <div className="metric-value">{Number(cpu.percent || 0).toFixed(1)}%</div>
    <p>{model}</p>
    <ConceptSparkline values={series} height={48} />
    <div className="metric-items">
      <Item label="Temperatur" value={reading(cpu.temperature_c, "°C")} />
      <Item label="Leistung" value={reading(cpu.power_w, "W")} />
      <Item label="Takt" value={reading(cpu.frequency_mhz, "MHz")} />
      {fan && <Item label={fan.name} value={reading(fan.rpm, "U/min")} />}
    </div>
  </div>;
}

export function MemoryCard({ metrics }: { metrics: Metrics }) {
  const memory = metrics.memory || {};
  const modules: Metrics[] = Array.isArray(metrics.hardware?.memory_modules) ? metrics.hardware.memory_modules : [];
  const hottest = modules.reduce<number | null>((max, module) => (isNumber(module.temperature_c) && (max === null || module.temperature_c > max) ? module.temperature_c : max), null);
  return <div className="metric-card">
    <div className="metric-title"><span>Arbeitsspeicher</span>{modules[0] && <VendorLogo name={modules[0].name} size={26} />}</div>
    <div className="metric-value">{Number(memory.used_gb || 0).toFixed(1)} GB</div>
    <p>von {Number(memory.total_gb || 0).toFixed(1)} GB belegt</p>
    <div className="metric-meter"><ConceptMeter value={Number(memory.percent || 0)} /></div>
    <div className="metric-items">
      <Item label="Auslastung" value={`${Number(memory.percent || 0).toFixed(1)}%`} />
      {modules.length > 0 && <Item label="Wärmstes Modul" value={reading(hottest, "°C", 1)} title={modules.map((module) => `${module.slot}: ${reading(module.temperature_c, "°C", 1)}`).join("\n")} />}
    </div>
  </div>;
}

export function GpuCard({ metrics, series }: { metrics: Metrics; series: number[] }) {
  const gpu = metrics.gpus?.[0] || {};
  const lhm = metrics.lhm_gpus?.[0] || {};
  const model = String(gpu.name || gpu.model || lhm.name || "Keine GPU erkannt");
  return <div className="metric-card">
    <div className="metric-title"><span>Grafikprozessor</span><VendorLogo name={model} size={26} /></div>
    <div className="metric-value">{metrics.gpus?.length ? `${Number(gpu.percent || 0).toFixed(1)}%` : "—"}</div>
    <p>{model}</p>
    <ConceptSparkline values={series} color="var(--purple)" height={48} />
    <div className="metric-items">
      <Item label="Temperatur" value={reading(lhm.temperature_c ?? gpu.temperature_c, "°C")} />
      {isNumber(lhm.hotspot_temperature_c) && <Item label="Hotspot" value={reading(lhm.hotspot_temperature_c, "°C")} />}
      <Item label="Leistung" value={reading(lhm.power_w ?? gpu.power_w, "W")} />
      {isNumber(lhm.fan_rpm) && <Item label="Lüfter" value={lhm.fan_rpm > 0 ? reading(lhm.fan_rpm, "U/min") : "Steht"} />}
    </div>
  </div>;
}

export function DrivesCard({ metrics }: { metrics: Metrics }) {
  const disks: Metrics[] = Array.isArray(metrics.disks) ? metrics.disks : [];
  const drives: Metrics[] = Array.isArray(metrics.hardware?.storage) ? metrics.hardware.storage : [];
  const byNumber = new Map(drives.filter((drive) => isNumber(drive.disk_number)).map((drive) => [drive.disk_number, drive]));
  const shown = new Set<number>();
  return <div className="detail-card drives-card">
    <div className="section-head"><div><h2>Laufwerke</h2></div></div>
    {disks.map((disk, index) => {
      const drive = isNumber(disk.disk_number) ? byNumber.get(disk.disk_number) : undefined;
      if (drive) shown.add(drive.disk_number);
      return <div className="disk-row" key={`${disk.mount || disk.name}-${index}`}>
        <div className="disk-head">
          {drive && <VendorLogo name={drive.name} size={22} />}
          <b>{disk.mount || disk.name || `Laufwerk ${index + 1}`}</b>
          {drive && <small className="disk-model">{drive.name}</small>}
          {drive && isNumber(drive.temperature_c) && <span className="disk-temp">{drive.temperature_c.toFixed(0)} °C</span>}
          <span className="disk-size">{Number(disk.used_gb || 0).toFixed(0)} / {Number(disk.total_gb || 0).toFixed(0)} GB</span>
        </div>
        <ConceptMeter value={Number(disk.percent || 0)} />
        <small>Lesen {rate(disk.read_mbps)} · Schreiben {rate(disk.write_mbps)}</small>
      </div>;
    })}
    {/* Drives without a Windows letter, e.g. the Linux disk of a dual boot. */}
    {drives.filter((drive) => !isNumber(drive.disk_number) || !shown.has(drive.disk_number)).map((drive, index) => <div className="disk-row other-drive" key={`other-${drive.name}-${index}`}>
      <div className="disk-head">
        <VendorLogo name={drive.name} size={22} />
        <b>{drive.name}</b>
        <small className="disk-model">ohne Laufwerksbuchstaben</small>
        {isNumber(drive.temperature_c) && <span className="disk-temp">{drive.temperature_c.toFixed(0)} °C</span>}
      </div>
    </div>)}
    {!disks.length && !drives.length && <div className="empty">Keine Laufwerksdaten vorhanden.</div>}
  </div>;
}

function SensorEditor({ current, withRole, onSave, onCancel }: {
  current: { name: string | null; role: SensorRole | null } | undefined;
  withRole: boolean;
  onSave: (name: string, role: SensorRole | null) => Promise<void>;
  onCancel: () => void;
}) {
  const [name, setName] = useState(current?.name || "");
  const [role, setRole] = useState<SensorRole | "">(current?.role || "");
  const [saving, setSaving] = useState(false);
  return <form className="sensor-editor" onSubmit={(event) => {
    event.preventDefault();
    setSaving(true);
    void onSave(name, role || null).finally(() => setSaving(false));
  }}>
    <input value={name} maxLength={48} placeholder="Name, z. B. Frontlüfter" onChange={(event) => setName(event.target.value)} autoFocus />
    {withRole && <select value={role} onChange={(event) => setRole(event.target.value as SensorRole | "")} aria-label="Rolle">
      <option value="">Keine Rolle</option>
      {ROLES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
    </select>}
    <button type="submit" className="outline-button" disabled={saving}>Speichern</button>
    <button type="button" className="link-button" onClick={onCancel}>Abbrechen</button>
  </form>;
}

export function MainboardCard({ metrics, isWindows, labels, canEdit, onLabel }: {
  metrics: Metrics;
  isWindows: boolean;
  labels: SensorLabels;
  canEdit: boolean;
  onLabel: (key: string, name: string, role: SensorRole | null) => Promise<void>;
}) {
  const [editing, setEditing] = useState<string | null>(null);
  const hardware = metrics.hardware || {};
  const { fans, temperatures, chip } = boardOf(metrics);
  const boardName = typeof hardware.components?.board === "string" ? hardware.components.board : null;
  const processes: Metrics[] = Array.isArray(metrics.processes) ? metrics.processes : [];
  const pawnio = typeof hardware.pawnio === "string" ? hardware.pawnio : null;
  const missingDriver = isWindows && hardware.provider === "librehardwaremonitor" && pawnio !== null && pawnio !== "running";
  const fastest = Math.max(1, ...fans.map((fan) => Number(fan.rpm) || 0));
  const row = (key: string, fallback: string, value: string, meter: number | null, withRole: boolean) => {
    const label = labels[key];
    if (editing === key) {
      return <div className="board-row editing" key={key}>
        <span className="board-default">{fallback}</span>
        <SensorEditor current={label} withRole={withRole} onCancel={() => setEditing(null)} onSave={async (name, role) => { await onLabel(key, name, role); setEditing(null); }} />
      </div>;
    }
    return <div className="board-row" key={key}>
      <span className="board-name">
        <b>{label?.name || fallback}</b>
        {label?.role && label.name !== ROLE_LABEL[label.role] && <em>{ROLE_LABEL[label.role]}</em>}
        {label?.name && <small>{fallback}</small>}
      </span>
      {meter !== null && <ConceptMeter value={meter} color="var(--blue)" />}
      <strong>{value}</strong>
      {canEdit && <button type="button" className="icon-edit" title="Benennen" aria-label={`${label?.name || fallback} benennen`} onClick={() => setEditing(key)}>✎</button>}
    </div>;
  };
  return <div className="detail-card mainboard-card">
    <div className="section-head">
      <div><h2>Mainboard</h2></div>
      <span className="board-model">{boardName && <VendorLogo name={boardName} size={26} />}<span>{boardName || chip || "Unbekannt"}</span></span>
    </div>
    {missingDriver && <div className="sensor-hint">
      <b>CPU- und Mainboard-Sensoren nicht verfügbar</b>
      {pawnio === "stopped"
        ? <p>Der Treiber PawnIO ist installiert, läuft aber nicht. Ein Neustart des PCs startet ihn.</p>
        : <p>CPU-Temperatur, CPU-Leistung und Mainboard-Lüfter benötigen den signierten Treiber PawnIO. Einmalig als Administrator installieren:</p>}
      {pawnio !== "stopped" && <code>{PAWNIO_COMMAND}</code>}
    </div>}
    {fans.length > 0 && <div className="board-group">
      <h3>Lüfter</h3>
      {fans.map((fan) => row(`fan:${fan.label}`, defaultName(String(fan.label)), `${reading(fan.rpm, "U/min")}${isNumber(fan.control_percent) ? ` · ${fan.control_percent} %` : ""}`, ((Number(fan.rpm) || 0) / fastest) * 100, true))}
    </div>}
    {temperatures.length > 0 && <div className="board-group">
      <h3>Temperaturen</h3>
      {temperatures.map((sensor) => row(`temp:${sensor.label}`, defaultName(String(sensor.label)), reading(sensor.value, "°C"), null, false))}
      <p className="sensor-note">Welcher Sensor zu welchem Anschluss gehört, hängt vom Mainboard ab. Nicht belegte Eingänge können unrealistische Werte zeigen.</p>
    </div>}
    {!fans.length && !temperatures.length && !missingDriver && <div className="empty">Keine Mainboard-Sensoren gemeldet.</div>}
    <div className="process-note">{processes.length ? `Top-Prozesse: ${processes.slice(0, 4).map((process) => `${process.name} ${Number(process.cpu || 0).toFixed(0)}%`).join(" · ")}` : "Keine Prozessdaten verfügbar."}</div>
  </div>;
}
