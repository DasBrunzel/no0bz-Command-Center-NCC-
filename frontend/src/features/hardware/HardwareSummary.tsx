import "./hardware.css";
import type { HardwareMetricName, HardwareStats } from "../../api/types";
import { Columns, LineChart } from "../../components/charts";
import { Reading, RelTime } from "../../components/ui";
import { fmt1, fmtDay } from "../../lib/format";

export const METRIC: Record<HardwareMetricName, { label: string; unit: string }> = {
  cpu_percent: { label: "CPU-Last", unit: "%" },
  cpu_temperature_c: { label: "CPU-Temperatur", unit: "°C" },
  cpu_power_w: { label: "CPU-Leistung", unit: "W" },
  cpu_fan_rpm: { label: "CPU-Lüfter", unit: "U/min" },
  gpu_percent: { label: "GPU-Last", unit: "%" },
  gpu_temperature_c: { label: "GPU-Temperatur", unit: "°C" },
  gpu_hotspot_c: { label: "GPU-Hotspot", unit: "°C" },
  gpu_power_w: { label: "GPU-Leistung", unit: "W" },
  memory_percent: { label: "RAM-Belegung", unit: "%" },
  ram_temperature_c: { label: "RAM-Temperatur", unit: "°C" },
  drive_temperature_c: { label: "Laufwerkstemperatur", unit: "°C" },
  case_fan_rpm: { label: "Gehäuselüfter", unit: "U/min" },
};

function kwh(wh: number): string {
  return wh >= 1000 ? `${fmt1(wh / 1000)} kWh` : `${Math.round(wh)} Wh`;
}

/** Averages, peaks and records over a period, plus daily energy and heat. */
export function HardwareSummary({ stats, showRecords = true }: { stats: HardwareStats; showRecords?: boolean }) {
  if (!stats.hours_covered) {
    return <p className="ink-3 small">Für diesen Zeitraum liegen noch keine Stundenwerte vor. Die Statistik füllt sich, sobald Agenten Messwerte schicken.</p>;
  }
  const temps = (["cpu_temperature_c", "gpu_temperature_c"] as const).filter((name) => stats.daily.some((day) => day.metrics[name]));
  return (
    <div className="hw-summary">
      <div className="hw-energy">
        <div>
          <span className="ink-3 small">Energie (CPU + GPU)</span>
          <p className="hw-big">{kwh(stats.energy_wh)}</p>
          <span className="ink-3 xsmall">aus {stats.hours_covered} Stunden Messdaten</span>
        </div>
        {stats.daily.length > 1 && (
          <Columns
            title="Energie pro Tag"
            unit="Wh"
            height={120}
            items={stats.daily.map((day) => ({ label: fmtDay(day.date), value: day.energy_wh }))}
            format={(value) => (value >= 1000 ? `${fmt1(value / 1000)}k` : String(Math.round(value)))}
          />
        )}
      </div>

      <table className="table">
        <caption className="visually-hidden">Durchschnitt und Spitzenwert je Messgröße</caption>
        <thead><tr><th>Messgröße</th><th className="r">Durchschnitt</th><th className="r">Spitze</th>{showRecords && <th>Rekord</th>}</tr></thead>
        <tbody>
          {stats.metrics.map((name) => {
            const summary = stats.summary[name];
            const record = stats.records[name];
            const meta = METRIC[name];
            if (!summary || !meta) return null;
            return (
              <tr key={name}>
                <td>{meta.label}</td>
                <td className="r"><Reading value={summary.average} unit={meta.unit} digits={meta.unit === "U/min" ? 0 : 1} /></td>
                <td className="r"><Reading value={summary.max} unit={meta.unit} /></td>
                {showRecords && <td className="small ink-2">{record ? <>{record.node_name ?? "?"}, <RelTime iso={record.at} /></> : "–"}</td>}
              </tr>
            );
          })}
        </tbody>
      </table>

      {temps.length > 0 && stats.daily.length > 1 && (
        <div>
          <h3 className="chart-title">Tagesspitzen der Temperatur</h3>
          <LineChart
            title="Höchste Temperatur pro Tag"
            unit="°C"
            labels={stats.daily.map((day) => fmtDay(day.date))}
            format={(value) => String(Math.round(value))}
            area={false}
            series={temps.map((name, index) => ({
              name: METRIC[name].label,
              color: index === 0 ? "var(--c-series-1)" : "var(--c-series-2)",
              values: stats.daily.map((day) => day.metrics[name]?.max ?? null),
            }))}
          />
        </div>
      )}
    </div>
  );
}
