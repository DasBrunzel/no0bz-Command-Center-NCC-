import React from "react";
import { SectionHead as ConceptSectionHead } from "./concept/components";

type Metrics = Record<string, any>;

const PAWNIO_COMMAND = "winget install --id namazso.PawnIO -e";

const reading = (value: unknown, unit: string, digits = 0) =>
  typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(digits)} ${unit}` : "—";
// LHM names unlabeled mainboard inputs "Temperature #3"; which header that is
// depends on the board, so NCC only numbers them.
const boardLabel = (label: string) => label.replace(/^Temperature #/, "Sensor ").replace(/^Fan #/, "Lüfter ");

function Row({ label, value }: { label: string; value: string }) {
  return <div className="sensor-row"><span>{label}</span><b>{value}</b></div>;
}

export function HardwareSensorsCard({ metrics, isWindows }: { metrics: Metrics; isWindows: boolean }) {
  const cpu = metrics.cpu || {};
  const gpu = metrics.gpus?.[0] || {};
  const lhmGpu = metrics.lhm_gpus?.[0] || {};
  const hardware = metrics.hardware || {};
  const processes: Metrics[] = Array.isArray(metrics.processes) ? metrics.processes : [];
  const storage: Metrics[] = Array.isArray(hardware.storage) ? hardware.storage : [];
  const memory: Metrics[] = Array.isArray(hardware.memory_modules) ? hardware.memory_modules : [];
  const board: Metrics | null = hardware.board && typeof hardware.board === "object" ? hardware.board : null;
  const boardFans: Metrics[] = Array.isArray(board?.fans) ? board.fans : [];
  const boardTemperatures: Metrics[] = Array.isArray(board?.temperatures) ? board.temperatures : [];
  const pawnio = typeof hardware.pawnio === "string" ? hardware.pawnio : null;
  const missingDriver = isWindows && hardware.provider === "librehardwaremonitor" && pawnio !== null && pawnio !== "running";
  return <div className="detail-card hardware-sensors">
    <ConceptSectionHead eyebrow="Hardware" title="Sensoren" />
    {missingDriver && <div className="sensor-hint">
      <b>CPU- und Mainboard-Sensoren nicht verfügbar</b>
      {pawnio === "stopped"
        ? <p>Der Treiber PawnIO ist installiert, läuft aber nicht. Ein Neustart des PCs startet ihn.</p>
        : <p>CPU-Temperatur, CPU-Leistung und Mainboard-Lüfter benötigen den signierten Treiber PawnIO. Einmalig als Administrator installieren:</p>}
      {pawnio !== "stopped" && <code>{PAWNIO_COMMAND}</code>}
    </div>}
    <div className="sensor-group">
      <Row label="CPU-Temperatur" value={reading(cpu.temperature_c, "°C", 1)} />
      <Row label="CPU-Leistung" value={reading(cpu.power_w, "W", 1)} />
      <Row label="GPU-Temperatur" value={reading(lhmGpu.temperature_c ?? gpu.temperature_c, "°C", 1)} />
      {typeof lhmGpu.hotspot_temperature_c === "number" && <Row label="GPU-Hotspot" value={reading(lhmGpu.hotspot_temperature_c, "°C", 1)} />}
      <Row label="GPU-Leistung" value={reading(lhmGpu.power_w ?? gpu.power_w, "W", 1)} />
      <Row label="GPU-Lüfter" value={reading(lhmGpu.fan_rpm, "U/min")} />
    </div>
    {storage.length > 0 && <div className="sensor-group">
      <h3>Laufwerke</h3>
      {storage.map((drive, index) => <Row key={`${drive.name}-${index}`} label={String(drive.name || `Laufwerk ${index + 1}`)} value={reading(drive.temperature_c, "°C")} />)}
    </div>}
    {memory.length > 0 && <div className="sensor-group">
      <h3>Arbeitsspeicher</h3>
      {memory.map((module, index) => <Row key={`${module.slot}-${index}`} label={`${module.slot || `Modul ${index + 1}`} · ${String(module.name || "").replace(/\s*\(#\d+\)$/, "")}`} value={reading(module.temperature_c, "°C", 1)} />)}
    </div>}
    {board && (boardFans.length > 0 || boardTemperatures.length > 0) && <div className="sensor-group">
      <h3>Mainboard <small>{board.chip}</small></h3>
      {boardFans.map((fan) => <Row key={fan.label} label={boardLabel(String(fan.label))} value={`${reading(fan.rpm, "U/min")}${typeof fan.control_percent === "number" ? ` · ${fan.control_percent} %` : ""}`} />)}
      {boardTemperatures.map((sensor) => <Row key={sensor.label} label={boardLabel(String(sensor.label))} value={reading(sensor.value, "°C")} />)}
      {boardTemperatures.length > 0 && <p className="sensor-note">Welcher Sensor zu welchem Anschluss gehört, hängt vom Mainboard ab. Nicht belegte Eingänge können unrealistische Werte zeigen.</p>}
    </div>}
    <div className="process-note">{processes.length ? `Top-Prozesse: ${processes.slice(0, 4).map((process) => `${process.name} ${Number(process.cpu || 0).toFixed(0)}%`).join(" · ")}` : "Keine Prozessdaten verfügbar."}</div>
  </div>;
}
