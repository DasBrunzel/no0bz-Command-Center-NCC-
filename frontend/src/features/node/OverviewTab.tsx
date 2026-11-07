import { lazy, Suspense, type ReactNode } from "react";
import type { FleetNode, Metrics } from "../../api/types";
import { Empty, Loading, Meter, Reading, RelTime } from "../../components/ui";
import { fmt1, fmtGb, fmtTime, num } from "../../lib/format";
import { VENDOR_NAME, cpuPercent, cpuTemp, gpuPercent, gpuTemp, isUnraid, memPercent, vendorOf } from "../../lib/node";
import { useTelemetry } from "./telemetry";

const LineChart = lazy(() => import("../../components/charts").then((module) => ({ default: module.LineChart })));

export function Vendor({ name }: { name: string | null | undefined }) {
  const vendor = vendorOf(name);
  return vendor ? <span className="vendor" data-vendor={vendor}>{VENDOR_NAME[vendor]}</span> : null;
}

export function OverviewTab({ node }: { node: FleetNode }) {
  const m = node.latest?.metrics;
  const telemetry = useTelemetry(node.node_id, node.online || !!node.latest);
  if (!m) {
    return (
      <Empty title="Noch keine Messwerte" icon="info">
        {node.online ? "Der Agent ist verbunden, hat aber noch keine Telemetrie geschickt." : <>Der Agent ist offline seit <RelTime iso={node.last_seen_at} /> und hat noch nie Messwerte geliefert.</>}
      </Empty>
    );
  }
  const stale = !node.online;
  const points = telemetry.data ?? [];
  const labels = points.map((point) => fmtTime(point.recorded_at));

  return (
    <div className="stack node-overview">
      {stale && (
        <p className="stale-note">
          Letzte bekannte Werte von <RelTime iso={node.latest?.recorded_at} /> – das Gerät ist gerade offline.
        </p>
      )}
      <div className="gauges" data-stale={stale || undefined}>
        <CpuGauge m={m} />
        <GpuGauge m={m} />
        <MemoryGauge m={m} />
        <NetGauge m={m} />
      </div>

      <section className="panel" aria-labelledby="history-title">
        <div className="panel-head">
          <h2 id="history-title">Verlauf</h2>
          <p>{points.length ? `Letzte ${points.length} Messpunkte` : "Wird geladen"}</p>
        </div>
        {telemetry.isPending ? (
          <Loading />
        ) : points.length < 2 ? (
          <p className="ink-3 small">Für einen Verlauf braucht es mindestens zwei Messpunkte.</p>
        ) : (
          <Suspense fallback={<Loading />}>
            <div className="history-charts">
              <div>
                <h3 className="chart-title">Auslastung</h3>
                <LineChart
                  title="Auslastung in Prozent"
                  unit="%"
                  max={100}
                  labels={labels}
                  format={(value) => String(Math.round(value))}
                  series={[
                    { name: "CPU", color: "var(--c-series-1)", values: points.map((point) => cpuPercent(point.metrics)) },
                    { name: "GPU", color: "var(--c-series-2)", values: points.map((point) => gpuPercent(point.metrics)) },
                    { name: "RAM", color: "var(--c-series-3)", values: points.map((point) => memPercent(point.metrics)) },
                  ]}
                />
              </div>
              <div>
                <h3 className="chart-title">Temperatur</h3>
                <LineChart
                  title="Temperaturen in Grad Celsius"
                  unit="°C"
                  labels={labels}
                  format={(value) => String(Math.round(value))}
                  series={[
                    { name: "CPU", color: "var(--c-series-1)", values: points.map((point) => cpuTemp(point.metrics)) },
                    { name: "GPU", color: "var(--c-series-2)", values: points.map((point) => gpuTemp(point.metrics)) },
                  ]}
                />
              </div>
            </div>
          </Suspense>
        )}
      </section>

      <div className="node-columns">
        <Disks m={m} />
        {isUnraid(node) ? <UnraidPanel m={m} /> : <Processes m={m} />}
      </div>

      <section className="panel" aria-labelledby="avail-title">
        <div className="panel-head"><h2 id="avail-title">Verfügbarkeit</h2></div>
        <dl className="kv">
          <dt>Verfügbar</dt><dd><Reading value={node.availability_percent} unit="%" digits={2} /> seit <RelTime iso={node.availability_started_at} /></dd>
          <dt>Aufgenommen</dt><dd><RelTime iso={node.created_at} /></dd>
          <dt>Agent</dt><dd>{node.agent_version ?? "–"}</dd>
          <dt>Maschinen-ID</dt><dd><code>{node.machine_id}</code></dd>
        </dl>
      </section>
    </div>
  );
}

function Gauge({ title, vendor, model, value, children }: { title: string; vendor?: string | null; model?: string | null; value: number | null; children: ReactNode }) {
  return (
    <section className="gauge">
      <header>
        <h2>{title}</h2>
        <Vendor name={vendor} />
      </header>
      <p className="gauge-value">{value == null ? "–" : Math.round(value)}<span className="unit">%</span></p>
      <Meter value={value} label={`${title}-Auslastung`} />
      {model && <p className="gauge-model" title={model}>{model}</p>}
      <dl className="gauge-facts">{children}</dl>
    </section>
  );
}

function CpuGauge({ m }: { m: Metrics }) {
  return (
    <Gauge title="CPU" vendor={m.cpu?.model} model={m.cpu?.model} value={cpuPercent(m)}>
      <div><dt>Temperatur</dt><dd><Reading value={cpuTemp(m)} unit="°C" /></dd></div>
      <div><dt>Leistung</dt><dd><Reading value={num(m.cpu?.power_w)} unit="W" /></dd></div>
      <div><dt>Takt</dt><dd><Reading value={num(m.cpu?.frequency_mhz)} unit="MHz" /></dd></div>
      <div><dt>Threads</dt><dd><Reading value={num(m.cpu?.logical_cores)} unit="" /></dd></div>
    </Gauge>
  );
}

function GpuGauge({ m }: { m: Metrics }) {
  const gpu = m.gpus?.[0];
  const lhm = m.lhm_gpus?.[0];
  if (!gpu && !lhm) {
    return (
      <section className="gauge gauge-empty"><header><h2>GPU</h2></header><p className="ink-3 small">Keine Grafikkarte gemeldet.</p></section>
    );
  }
  const name = gpu?.name ?? lhm?.name;
  return (
    <Gauge title="GPU" vendor={name} model={name} value={gpuPercent(m)}>
      <div><dt>Temperatur</dt><dd><Reading value={gpuTemp(m)} unit="°C" /></dd></div>
      {num(lhm?.hotspot_temperature_c) != null && <div><dt>Hotspot</dt><dd><Reading value={num(lhm?.hotspot_temperature_c)} unit="°C" /></dd></div>}
      <div><dt>Leistung</dt><dd><Reading value={num(lhm?.power_w) ?? num(gpu?.power_w)} unit="W" /></dd></div>
      <div><dt>VRAM</dt><dd>{gpu?.vram_total_gb ? `${fmt1(gpu.vram_used_gb ?? 0)} / ${fmtGb(gpu.vram_total_gb)}` : "–"}</dd></div>
    </Gauge>
  );
}

function MemoryGauge({ m }: { m: Metrics }) {
  return (
    <Gauge title="RAM" value={memPercent(m)} model={m.memory?.total_gb ? `${fmtGb(m.memory.total_gb)} Arbeitsspeicher` : null}>
      <div><dt>Belegt</dt><dd>{m.memory?.used_gb != null ? fmtGb(m.memory.used_gb) : "–"}</dd></div>
      <div><dt>Frei</dt><dd>{m.memory?.available_gb != null ? fmtGb(m.memory.available_gb) : m.memory?.free_gb != null ? fmtGb(m.memory.free_gb) : "–"}</dd></div>
      {m.swap?.total_gb ? <div><dt>Auslagerung</dt><dd><Reading value={num(m.swap.percent)} unit="%" /></dd></div> : null}
    </Gauge>
  );
}

function NetGauge({ m }: { m: Metrics }) {
  return (
    <section className="gauge">
      <header><h2>Netzwerk</h2></header>
      <p className="gauge-value gauge-net"><span>↓</span><Reading value={num(m.network?.download_mbps)} unit="Mbit/s" digits={1} /></p>
      <p className="gauge-value gauge-net"><span>↑</span><Reading value={num(m.network?.upload_mbps)} unit="Mbit/s" digits={1} /></p>
      {m.network?.interface && <p className="gauge-model">{m.network.interface}</p>}
    </section>
  );
}

function Disks({ m }: { m: Metrics }) {
  const disks = m.disks ?? [];
  return (
    <section className="panel" aria-labelledby="disks-title">
      <div className="panel-head"><h2 id="disks-title">Laufwerke</h2></div>
      {disks.length === 0 ? (
        <p className="ink-3 small">Keine Laufwerke gemeldet.</p>
      ) : (
        <table className="table">
          <thead><tr><th>Laufwerk</th><th>Belegt</th><th className="r">Größe</th><th className="r">Temp.</th></tr></thead>
          <tbody>
            {disks.map((disk, index) => (
              <tr key={`${disk.name}-${index}`}>
                <td>{disk.name ?? disk.mount}{disk.spinning === false && <span className="badge" style={{ marginInlineStart: 8 }}>schläft</span>}</td>
                <td><span className="meter-cell"><Meter value={num(disk.percent)} label={`Belegung ${disk.name}`} caution={85} stop={95} /><span className="num">{Math.round(disk.percent ?? 0)}<span className="unit">%</span></span></span></td>
                <td className="r">{fmtGb(disk.total_gb)}</td>
                <td className="r"><Reading value={num(disk.temperature_c)} unit="°C" /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function Processes({ m }: { m: Metrics }) {
  const list = [...(m.processes ?? [])].sort((a, b) => b.cpu - a.cpu).slice(0, 8);
  return (
    <section className="panel" aria-labelledby="proc-title">
      <div className="panel-head"><h2 id="proc-title">Prozesse</h2><p>nach CPU-Last</p></div>
      {list.length === 0 ? (
        <p className="ink-3 small">Der Agent meldet keine Prozessliste.</p>
      ) : (
        <table className="table">
          <thead><tr><th>Prozess</th><th className="r">CPU</th><th className="r">RAM</th></tr></thead>
          <tbody>{list.map((proc) => <tr key={proc.pid}><td>{proc.name}</td><td className="r"><Reading value={proc.cpu} unit="%" digits={1} /></td><td className="r"><Reading value={proc.memory} unit="%" digits={1} /></td></tr>)}</tbody>
        </table>
      )}
    </section>
  );
}

function UnraidPanel({ m }: { m: Metrics }) {
  const containers = m.containers ?? [];
  const vms = m.vms ?? [];
  const running = (state?: string) => /running|started/i.test(state ?? "");
  return (
    <section className="panel" aria-labelledby="unraid-title">
      <div className="panel-head">
        <h2 id="unraid-title">Unraid</h2>
        <p>Version {m.unraid?.version ?? "?"} · Array {m.unraid?.array_state === "STARTED" ? "läuft" : (m.unraid?.array_state ?? "unbekannt")}</p>
      </div>
      <h3 className="chart-title">Container</h3>
      {containers.length === 0 ? <p className="ink-3 small">Keine Docker-Container gemeldet.</p> : (
        <ul className="plain chips" role="list">
          {containers.map((item, index) => {
            const name = item.names?.[0]?.replace(/^\//, "") ?? item.name ?? `Container ${index + 1}`;
            return <li key={name + index} className="badge" data-tone={running(item.state) ? "go" : undefined}>{name}</li>;
          })}
        </ul>
      )}
      <h3 className="chart-title mt-4">VMs</h3>
      {vms.length === 0 ? <p className="ink-3 small">Keine virtuellen Maschinen.</p> : (
        <ul className="plain chips" role="list">
          {vms.map((item, index) => <li key={index} className="badge" data-tone={running(item.state) ? "go" : undefined}>{item.name ?? `VM ${index + 1}`}</li>)}
        </ul>
      )}
    </section>
  );
}
