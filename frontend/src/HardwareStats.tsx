import React, { useEffect, useMemo, useState } from "react";
import { SectionHead as ConceptSectionHead } from "./concept/components";

type Summary = { average: number; max: number };
type HardwareStats = {
  days: number;
  metrics: string[];
  summary: Record<string, Summary>;
  records: Record<string, { value: number; at: string; node_name: string | null }>;
  energy_wh: number;
  daily: { date: string; energy_wh: number; metrics: Record<string, Summary> }[];
  hours_covered: number;
};
type StatsNode = { node_id: string; display_name: string; platform: string; metadata: Record<string, unknown> };

const PERIODS = [{ days: 7, label: "7 Tage" }, { days: 30, label: "30 Tage" }, { days: 365, label: "1 Jahr" }, { days: 0, label: "Gesamt" }];
export const METRIC_INFO: Record<string, { label: string; unit: string }> = {
  cpu_percent: { label: "CPU-Last", unit: "%" },
  cpu_temperature_c: { label: "CPU-Temperatur", unit: "°C" },
  cpu_power_w: { label: "CPU-Leistung", unit: "W" },
  cpu_fan_rpm: { label: "CPU-Lüfter", unit: "U/min" },
  gpu_percent: { label: "GPU-Last", unit: "%" },
  gpu_temperature_c: { label: "GPU-Temperatur", unit: "°C" },
  gpu_hotspot_c: { label: "GPU-Hotspot", unit: "°C" },
  gpu_power_w: { label: "GPU-Leistung", unit: "W" },
  memory_percent: { label: "RAM-Auslastung", unit: "%" },
  ram_temperature_c: { label: "RAM-Temperatur", unit: "°C" },
  drive_temperature_c: { label: "SSD-Temperatur", unit: "°C" },
  case_fan_rpm: { label: "Gehäuselüfter", unit: "U/min" },
};
const authHeaders = (token: string): Record<string, string> => (token ? { "X-NCC-Dashboard-Token": token } : {});
const energy = (wh: number) => (wh >= 1000 ? `${(wh / 1000).toLocaleString("de-DE", { maximumFractionDigits: 1 })} kWh` : `${Math.round(wh)} Wh`);
const shortDate = (date: string) => new Date(`${date}T12:00:00`).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });

type Series = { key: string; label: string; color: string; values: (number | null)[] };

/** Line chart with a shared hover readout; one y-axis, nulls leave gaps. */
function LineChart({ dates, series, unit }: { dates: string[]; series: Series[]; unit: string }) {
  const [hovered, setHovered] = useState<number | null>(null);
  const width = 600, height = 180, padTop = 8, padBottom = 4;
  const all = series.flatMap((item) => item.values.filter((value): value is number => value !== null));
  if (!all.length || dates.length === 0) return <div className="empty">Noch keine Messwerte in diesem Zeitraum.</div>;
  const min = Math.max(0, Math.floor(Math.min(...all) / 10) * 10 - 10);
  const max = Math.ceil(Math.max(...all) / 10) * 10 + 5;
  const x = (index: number) => (dates.length === 1 ? width / 2 : (index / (dates.length - 1)) * width);
  const y = (value: number) => padTop + (1 - (value - min) / Math.max(1, max - min)) * (height - padTop - padBottom);
  const path = (values: (number | null)[]) => values.reduce((result, value, index) => {
    if (value === null) return result;
    const previous = index > 0 ? values[index - 1] : null;
    return `${result}${previous === null ? "M" : "L"}${x(index).toFixed(1)},${y(value).toFixed(1)} `;
  }, "");
  const focus = hovered ?? dates.length - 1;
  const grid = [min, (min + max) / 2, max];
  return <div className="line-chart">
    <div className="line-legend">
      <span className="line-date">{hovered !== null ? shortDate(dates[focus]) : "Zuletzt"}</span>
      {series.map((item) => <span key={item.key}><i style={{ background: item.color }} />{item.label} <b>{item.values[focus] !== null ? `${item.values[focus]!.toFixed(0)} ${unit}` : "—"}</b></span>)}
    </div>
    <div className="line-plot">
      <div className="line-grid">{[...grid].reverse().map((value) => <span key={value}>{value.toFixed(0)}</span>)}</div>
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label={series.map((item) => item.label).join(", ")}
        onMouseMove={(event) => {
          const box = event.currentTarget.getBoundingClientRect();
          const ratio = (event.clientX - box.left) / box.width;
          setHovered(Math.max(0, Math.min(dates.length - 1, Math.round(ratio * (dates.length - 1)))));
        }}
        onMouseLeave={() => setHovered(null)}>
        {grid.map((value) => <line key={value} x1={0} x2={width} y1={y(value)} y2={y(value)} className="grid-line" />)}
        {hovered !== null && <line x1={x(hovered)} x2={x(hovered)} y1={0} y2={height} className="cross-line" />}
        {series.map((item) => <path key={item.key} d={path(item.values)} fill="none" stroke={item.color} strokeWidth={2} vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />)}
        {series.map((item) => item.values[focus] !== null && <circle key={`${item.key}-dot`} cx={x(focus)} cy={y(item.values[focus]!)} r={4} fill={item.color} stroke="var(--panel)" strokeWidth={2} vectorEffect="non-scaling-stroke" />)}
      </svg>
    </div>
    <div className="line-axis"><span>{shortDate(dates[0])}</span><span>{shortDate(dates[dates.length - 1])}</span></div>
  </div>;
}

export function HardwareStatistics({ nodes, token }: { nodes: StatsNode[]; token: string }) {
  const candidates = useMemo(() => nodes.filter((node) => node.metadata.source !== "unraid-api"), [nodes]);
  const [nodeId, setNodeId] = useState(() => candidates.find((node) => node.platform === "windows")?.node_id || candidates[0]?.node_id || "");
  const [days, setDays] = useState(30);
  const [stats, setStats] = useState<HardwareStats | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!nodeId && candidates[0]) setNodeId(candidates[0].node_id);
  }, [candidates, nodeId]);
  useEffect(() => {
    if (!nodeId) return;
    let current = true;
    setStats(null);
    const load = async () => {
      const params = new URLSearchParams({ days: String(days), node_id: nodeId, utc_offset_minutes: String(-new Date().getTimezoneOffset()) });
      try {
        const response = await fetch(`/api/v1/fleet/hardware/stats?${params}`, { headers: authHeaders(token) });
        if (!response.ok) throw new Error("REQUEST");
        const value = await response.json() as HardwareStats;
        if (current) { setStats(value); setFailed(false); }
      } catch { if (current) setFailed(true); }
    };
    void load();
    const timer = window.setInterval(() => { if (document.visibilityState === "visible") void load(); }, 120_000);
    return () => { current = false; window.clearInterval(timer); };
  }, [days, nodeId, token]);

  const dates = stats?.daily.map((day) => day.date) || [];
  const daily = (metric: string, field: "average" | "max") => stats?.daily.map((day) => day.metrics[metric]?.[field] ?? null) || [];
  const has = (metric: string) => !!stats?.summary[metric];
  const temperatures: Series[] = [
    { key: "cpu", label: "CPU", color: "var(--series-1)", values: daily("cpu_temperature_c", "max") },
    { key: "gpu", label: "GPU", color: "var(--series-2)", values: daily("gpu_temperature_c", "max") },
    { key: "drive", label: "SSD", color: "var(--series-3)", values: daily("drive_temperature_c", "max") },
    { key: "ram", label: "RAM", color: "var(--series-4)", values: daily("ram_temperature_c", "max") },
  ].filter((item) => item.values.some((value) => value !== null));
  const loads: Series[] = [
    { key: "cpu", label: "CPU", color: "var(--series-1)", values: daily("cpu_percent", "average") },
    { key: "gpu", label: "GPU", color: "var(--series-2)", values: daily("gpu_percent", "average") },
    { key: "ram", label: "RAM", color: "var(--series-3)", values: daily("memory_percent", "average") },
  ].filter((item) => item.values.some((value) => value !== null));
  const power: Series[] = [
    { key: "cpu", label: "CPU", color: "var(--series-1)", values: daily("cpu_power_w", "average") },
    { key: "gpu", label: "GPU", color: "var(--series-2)", values: daily("gpu_power_w", "average") },
  ].filter((item) => item.values.some((value) => value !== null));
  const tile = (metric: string, field: "average" | "max", title: string) => {
    const info = METRIC_INFO[metric];
    const value = stats?.summary[metric]?.[field];
    return <div><small>{title}</small><strong>{value !== undefined ? <>{value.toFixed(0)}<small>{info.unit}</small></> : "—"}</strong><p>{field === "max" && stats?.records[metric] ? new Date(stats.records[metric].at).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" }) : field === "average" ? "Durchschnitt" : ""}</p></div>;
  };

  return <>
    <div className="filter-bar playtime-filters">
      <div className="segmented">{PERIODS.map((period) => <button type="button" key={period.days} className={days === period.days ? "selected" : ""} onClick={() => setDays(period.days)}>{period.label}</button>)}</div>
      <select value={nodeId} onChange={(event) => setNodeId(event.target.value)} aria-label="Gerät">
        {candidates.map((node) => <option key={node.node_id} value={node.node_id}>{node.display_name}</option>)}
      </select>
    </div>
    {failed && !stats && <div className="detail-card empty">Die Hardware-Statistik konnte nicht geladen werden.</div>}
    {!failed && !stats && nodeId && <div className="detail-card empty">Hardware-Statistik wird geladen …</div>}
    {stats && stats.hours_covered === 0 && <div className="detail-card empty playtime-empty"><h2>Noch keine Hardware-Werte</h2><p>Der Server rechnet ältere Messwerte im Hintergrund nach. Schau in ein paar Minuten noch einmal vorbei.</p></div>}
    {stats && stats.hours_covered > 0 && <>
      <div className="stats-summary playtime-summary">
        {tile("cpu_temperature_c", "average", "Ø CPU-Temperatur")}
        {tile("cpu_temperature_c", "max", "Heißeste CPU")}
        {tile("gpu_temperature_c", "max", "Heißeste GPU")}
        <div><small>Energie CPU + GPU</small><strong className="playtime-title">{stats.energy_wh > 0 ? energy(stats.energy_wh) : "—"}</strong><p>{PERIODS.find((period) => period.days === days)?.label}</p></div>
      </div>
      <div className="stats-layout">
        <div className="detail-card">
          <ConceptSectionHead eyebrow="Höchstwert pro Tag" title="Temperaturen" />
          <LineChart dates={dates} series={temperatures} unit="°C" />
        </div>
        <div className="detail-card">
          <ConceptSectionHead eyebrow="Durchschnitt pro Tag" title="Auslastung" />
          <LineChart dates={dates} series={loads} unit="%" />
        </div>
      </div>
      <div className="stats-layout">
        <div className="detail-card">
          <ConceptSectionHead eyebrow="Durchschnitt pro Tag" title="Leistungsaufnahme" />
          {power.length ? <LineChart dates={dates} series={power} unit="W" /> : <div className="empty">Dieses Gerät meldet keine Leistungswerte.</div>}
        </div>
        <div className="detail-card">
          <ConceptSectionHead eyebrow="Bestwerte" title="Rekorde" />
          <div className="table-scroll"><table className="game-hardware">
            <thead><tr><th>Messwert</th><th>Ø</th><th>Höchstwert</th><th>Wann</th></tr></thead>
            <tbody>{stats.metrics.filter(has).map((metric) => {
              const info = METRIC_INFO[metric] || { label: metric, unit: "" };
              const record = stats.records[metric];
              return <tr key={metric}>
                <td>{info.label}</td>
                <td>{stats.summary[metric].average.toFixed(0)} {info.unit}</td>
                <td><b>{record ? `${record.value.toFixed(0)} ${info.unit}` : "—"}</b></td>
                <td>{record ? new Date(record.at).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—"}</td>
              </tr>;
            })}</tbody>
          </table></div>
        </div>
      </div>
    </>}
  </>;
}
