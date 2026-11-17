import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { POLL, api, qk } from "../../api/endpoints";
import type { AndroidAppConfig, AndroidMetrics, FleetNode, Metrics } from "../../api/types";
import { useCan } from "../../app/auth";
import { useToast } from "../../components/toast";
import { Empty, Lamp, Meter, Reading, RelTime } from "../../components/ui";
import { fmtGb, num } from "../../lib/format";
import { memPercent } from "../../lib/node";

const THERMAL: Record<string, string> = {
  none: "Normal", light: "Leicht warm", moderate: "Warm", severe: "Heiß",
  critical: "Kritisch", emergency: "Notfall", shutdown: "Abschaltung",
};
const SOURCE: Record<string, string> = { none: "Akku", ac: "Netzteil", usb: "USB", wireless: "Kabellos", dock: "Dock" };
const NETWORK: Record<string, string> = { wifi: "WLAN", cellular: "Mobilfunk", ethernet: "Ethernet", other: "Sonstiges", unknown: "unbekannt" };

/**
 * Overview of an Android app node. While this view is open it polls the live
 * endpoint every two seconds, which tells the phone to stream; otherwise it
 * shows the last stored sample.
 */
export function AndroidLive({ node }: { node: FleetNode }) {
  const live = useQuery({
    queryKey: qk.live(node.node_id),
    queryFn: () => api.fleet.live(node.node_id),
    refetchInterval: POLL.live,
    refetchIntervalInBackground: false,
  });
  const liveMetrics = live.data?.live ? live.data.metrics : null;
  const m: Metrics | undefined = liveMetrics ?? node.latest?.metrics;
  const recordedAt = live.data?.live ? live.data.recorded_at : node.latest?.recorded_at;

  if (!m) {
    return (
      <Empty title="Noch keine Messwerte" icon="info">
        {live.data?.connected ? "Das Handy ist verbunden – die ersten Live-Werte kommen gleich." : "Die App hat noch keine Messwerte geschickt."}
      </Empty>
    );
  }
  const a = (m.android ?? {}) as AndroidMetrics;
  const disk = m.disks?.[0];
  const battery = m.battery;

  return (
    <div className="stack node-overview android-live">
      <p className="android-live-state">
        {liveMetrics ? (
          <><Lamp state="go" size="s" blink label="Live" /> <strong>Live</strong> · alle 2 Sekunden vom Handy</>
        ) : live.data?.connected ? (
          <><Lamp state="caution" size="s" blink label="Verbindet" /> Handy verbunden, Live-Werte starten …</>
        ) : (
          <><Lamp state="off" size="s" label="Nicht live" /> Letzter gespeicherter Stand <RelTime iso={recordedAt} /> – Live-Ansicht, sobald die App verbunden ist</>
        )}
      </p>

      <div className="gauges" data-stale={!liveMetrics && !node.online ? true : undefined}>
        <Tile title="Akku" value={num(battery?.percent)} caution={101} stop={101} model={batteryLine(a)}>
          <Fact label="Temperatur"><Reading value={num(a.battery?.temperature_c)} unit="°C" digits={1} /></Fact>
          <Fact label="Quelle">{SOURCE[a.battery?.source ?? ""] ?? "–"}</Fact>
          <Fact label="Ladezyklen"><Reading value={num(a.battery?.cycles)} unit="" /></Fact>
          <Fact label="Spannung"><Reading value={a.battery?.voltage_mv != null ? a.battery.voltage_mv / 1000 : null} unit="V" digits={2} /></Fact>
        </Tile>
        <Tile title="RAM" value={memPercent(m)} model={a.ram_advertised_gb ? `${a.ram_advertised_gb} GB Arbeitsspeicher` : null}>
          <Fact label="Belegt">{m.memory?.used_gb != null ? fmtGb(m.memory.used_gb) : "–"}</Fact>
          <Fact label="Frei">{m.memory?.available_gb != null ? fmtGb(m.memory.available_gb) : "–"}</Fact>
        </Tile>
        <Tile title="Speicher" value={num(disk?.percent)} model={disk?.total_gb != null ? `${fmtGb(disk.total_gb)} intern` : null}>
          <Fact label="Belegt">{disk?.used_gb != null ? fmtGb(disk.used_gb) : "–"}</Fact>
          <Fact label="Frei">{disk?.used_gb != null && disk.total_gb != null ? fmtGb(disk.total_gb - disk.used_gb) : "–"}</Fact>
        </Tile>
        <Tile title="Taktlast" value={num(a.clock_load)} caution={101} stop={101} model={a.soc ?? m.cpu?.model ?? null}>
          <Fact label="Ø Takt"><Reading value={num(m.cpu?.frequency_mhz)} unit="MHz" /></Fact>
          <Fact label="Kerne"><Reading value={num(m.cpu?.logical_cores)} unit="" /></Fact>
          <Fact label="Thermik">{THERMAL[a.thermal ?? ""] ?? "–"}</Fact>
        </Tile>
      </div>

      <div className="node-columns">
        <section className="panel" aria-labelledby="android-cores-title">
          <div className="panel-head">
            <h2 id="android-cores-title">Kerne</h2>
            <p>{a.architecture ?? "–"}</p>
          </div>
          <Cores a={a} />
          <p className="form-hint mt-4">Taktlast = aktueller Takt ÷ Maximaltakt. Android gibt Apps keine echte Kernauslastung heraus.</p>
        </section>
        <section className="panel" aria-labelledby="android-device-title">
          <div className="panel-head"><h2 id="android-device-title">Gerät</h2></div>
          <dl className="android-facts">
            <Fact label="Modell">{[a.manufacturer, a.model].filter(Boolean).join(" ") || "–"}{a.emulator ? " (Emulator)" : ""}</Fact>
            <Fact label="System">{m.system?.platform ?? "–"}{a.sdk ? ` · SDK ${a.sdk}` : ""}</Fact>
            <Fact label="Sicherheitspatch">{a.security_patch ?? "–"}</Fact>
            <Fact label="SoC">{a.soc ?? "–"}{a.soc_code && a.soc_code !== a.soc ? ` (${a.soc_code})` : ""}</Fact>
            <Fact label="Netz">{NETWORK[a.network?.type ?? ""] ?? "–"}{a.network?.vpn ? " · über VPN" : ""}</Fact>
          </dl>
        </section>
      </div>
      <AppSettings node={node} connected={!!live.data?.connected} />
    </div>
  );
}

const INTERVALS: Array<{ value: NonNullable<AndroidAppConfig["interval_seconds"]>; label: string }> = [
  { value: 30, label: "30 Sekunden" }, { value: 60, label: "1 Minute" }, { value: 120, label: "2 Minuten" }, { value: 300, label: "5 Minuten" },
];
const RULES: Array<{ value: NonNullable<AndroidAppConfig["upload_rule"]>; label: string }> = [
  { value: "wifi_charging", label: "WLAN + Laden" }, { value: "immediate", label: "Sofort" },
];

/** Measuring interval and upload rule of the phone, changed remotely over the live channel. */
function AppSettings({ node, connected }: { node: FleetNode; connected: boolean }) {
  const can = useCan();
  const toast = useToast();
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  if (!can.manage(node)) return null;
  const interval = Number(node.metadata?.heartbeat_interval_seconds) || null;
  const rule = typeof node.metadata?.upload_rule === "string" ? node.metadata.upload_rule : null;

  const change = async (config: AndroidAppConfig, text: string) => {
    setBusy(true);
    try {
      await api.fleet.setAppConfig(node.node_id, config);
      toast.ok(`${text} Das Handy übernimmt es sofort; hier steht es nach dem nächsten Lebenszeichen.`);
      window.setTimeout(() => void client.invalidateQueries({ queryKey: qk.node(node.node_id) }), 4000);
    } catch (error) {
      toast.fail(error);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel" aria-labelledby="android-settings-title">
      <div className="panel-head">
        <h2 id="android-settings-title">App-Einstellungen</h2>
        <p>{connected ? "Änderungen gehen sofort ans Handy" : "Nur möglich, solange das Handy verbunden ist"}</p>
      </div>
      <div className="android-settings">
        <label className="field">
          <span>Messintervall</span>
          <select className="select" value={interval ?? ""} disabled={!connected || busy}
            onChange={(event) => void change({ interval_seconds: Number(event.target.value) as AndroidAppConfig["interval_seconds"] }, "Messintervall geändert.")}>
            {interval === null && <option value="">unbekannt</option>}
            {INTERVALS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>
        <label className="field">
          <span>Upload</span>
          <select className="select" value={rule ?? ""} disabled={!connected || busy}
            onChange={(event) => void change({ upload_rule: event.target.value as AndroidAppConfig["upload_rule"] }, "Upload-Regel geändert.")}>
            {rule === null && <option value="">unbekannt</option>}
            {RULES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>
      </div>
    </section>
  );
}

function batteryLine(a: AndroidMetrics): string | null {
  if (!a.battery) return null;
  if (a.battery.full) return "voll";
  return a.battery.charging ? "lädt" : "entlädt";
}

function Cores({ a }: { a: AndroidMetrics }) {
  const cores = a.cores ?? [];
  if (!cores.length) return <p className="ink-3 small">Keine Kerndaten.</p>;
  const clusters = a.clusters?.length ? [...a.clusters].sort((x, y) => (y.max_mhz ?? 0) - (x.max_mhz ?? 0)) : [{ name: "Kerne", cores: cores.map((core) => core.id) }];
  return (
    <div className="android-cores">
      {clusters.map((cluster) => (
        <div key={cluster.name + cluster.cores.join(",")} className="android-cluster">
          <h3 className="chart-title">
            {cluster.cores.length}× {cluster.name}
            {"max_mhz" in cluster && cluster.max_mhz ? <span className="ink-3"> · max {(cluster.max_mhz / 1000).toFixed(2).replace(".", ",")} GHz</span> : null}
          </h3>
          {cluster.cores.map((id) => {
            const core = cores.find((item) => item.id === id);
            return (
              <div key={id} className="android-core">
                <span className="ink-3">CPU {id}</span>
                <Meter value={core?.clock_load ?? null} label={`CPU ${id} Taktlast`} caution={101} stop={101} />
                <span className="num">{!core?.online ? "aus" : core.mhz != null ? `${core.mhz} MHz` : "n/a"}</span>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

function Tile({ title, value, model, children, caution, stop }: {
  title: string; value: number | null; model?: string | null; children: ReactNode; caution?: number; stop?: number;
}) {
  return (
    <section className="gauge">
      <header><h2>{title}</h2></header>
      <p className="gauge-value">{value == null ? "–" : Math.round(value)}<span className="unit">%</span></p>
      <Meter value={value} label={title} caution={caution} stop={stop} />
      {model && <p className="gauge-model" title={model}>{model}</p>}
      <dl className="gauge-facts">{children}</dl>
    </section>
  );
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return <div><dt>{label}</dt><dd>{children}</dd></div>;
}
