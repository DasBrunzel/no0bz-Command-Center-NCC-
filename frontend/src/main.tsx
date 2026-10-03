import React, { useCallback, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  ArrowDownToLine,
  ArrowUpToLine,
  BarChart3,
  Ban,
  Bell,
  Boxes,
  Check,
  ChevronRight,
  Clock3,
  Copy,
  Cpu,
  HardDrive,
  KeyRound,
  LayoutDashboard,
  MemoryStick,
  Menu,
  MonitorCog,
  Moon,
  Network,
  RefreshCw,
  Search,
  Server,
  Settings,
  ShieldCheck,
  Signal,
  Trash2,
  UserPlus,
  Wifi,
  WifiOff,
  X,
} from "lucide-react";
import "./index.css";
import "./enrollment.css";
import "./device-lifecycle.css";

type Metrics = Record<string, any>;
type Telemetry = {
  sample_id: string | null;
  recorded_at: string;
  metrics: Metrics;
};
type Node = {
  node_id: string;
  machine_id: string;
  display_name: string;
  platform: string;
  approved: boolean;
  access_role: AccessRole;
  online: boolean;
  agent_version: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  last_seen_at: string | null;
  fleet_group_id: string;
  fleet_position: number;
  latest: Telemetry | null;
};
type FleetGroup = { group_id: string; name: string; position: number };
type FleetPlacement = { node_id: string; group_id: string; position: number };
type Summary = {
  total_nodes: number;
  online_nodes: number;
  offline_nodes: number;
  pending_nodes: number;
  telemetry_points: number;
  server_time: string;
};
type NetworkUsageSummary = {
  period_start: string;
  received_bytes: number;
  sent_bytes: number;
  samples: number;
  available: boolean;
};
type Theme =
  | "nightmare"
  | "cachyos"
  | "cyber"
  | "oled"
  | "light"
  | "matrix"
  | "dracula"
  | "nordic"
  | "amber"
  | "glass"
  | "terminal"
  | "aurora"
  | "orbit"
  | "blueprint"
  | "studio";
type Invitation = {
  token_id: string;
  name: string;
  status: "ready" | "bound" | "expired" | "revoked";
  node_id: string | null;
  node_name: string | null;
  created_at: string;
  expires_at: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
};
type IssuedInvitation = Invitation & { token: string };
type AccessRole = "commander" | "beta_tester";
type DashboardAccess = { access_role: AccessRole };
type IssuedAdminCode = { code: string; expires_at: string; access_role: AccessRole };
type AdminCode = {
  code_id: string;
  label: string;
  status: "ready" | "used" | "expired" | "revoked";
  created_at: string;
  expires_at: string;
  used_at: string | null;
  revoked_at: string | null;
  access_role: AccessRole;
};
type AgentPairing = {
  pairing_id: string;
  display_name: string;
  platform: string;
  status: "waiting" | "approved" | "claimed" | "expired" | "cancelled";
  created_at: string;
  expires_at: string;
};
type FleetAlert = {
  id: string;
  title: string;
  detail: string;
  severity: "warning" | "critical";
};
type AlertRecord = {
  alert_id: string;
  node_id: string;
  display_name: string;
  kind: string;
  severity: "warning" | "critical";
  active: boolean;
  message: string;
  opened_at: string;
  updated_at: string;
  resolved_at: string | null;
};
type AlertPolicy = {
  cpu_threshold: number;
  memory_threshold: number;
  gpu_threshold: number;
  disk_threshold: number;
};
type Page = "fleet" | "statistics" | "alerts" | "onboarding" | "settings";

const THEMES: { id: Theme; name: string; color: string }[] = [
  { id: "nightmare", name: "Nightmare Red", color: "#ff334f" },
  { id: "cachyos", name: "CachyOS Cyan", color: "#18d7ec" },
  { id: "cyber", name: "Cyber Neon", color: "#ff35d3" },
  { id: "oled", name: "Dark Matter OLED", color: "#e8edf5" },
  { id: "light", name: "Clean Light", color: "#d52f4b" },
  { id: "matrix", name: "Matrix Hacker", color: "#36f276" },
  { id: "dracula", name: "Dracula", color: "#ff6680" },
  { id: "nordic", name: "Nordic Frost", color: "#88c0d0" },
  { id: "amber", name: "Retro Amber", color: "#ffb52e" },
  { id: "glass", name: "Glass Command", color: "#79e6ff" },
  { id: "terminal", name: "Terminal Grid", color: "#9cff57" },
  { id: "aurora", name: "Aurora Horizon", color: "#b79cff" },
  { id: "orbit", name: "Orbit Console", color: "#53d7ff" },
  { id: "blueprint", name: "Blueprint Dock", color: "#68a7ff" },
  { id: "studio", name: "Studio Deck", color: "#ff8eb5" },
];
const num = (value: unknown) =>
  typeof value === "number" && Number.isFinite(value) ? value : 0;
const metric = (value: unknown, digits = 1) =>
  typeof value === "number" && Number.isFinite(value)
    ? value.toFixed(digits)
    : "—";
const ago = (value: string | null) => {
  if (!value) return "Noch nie";
  const seconds = Math.max(
    0,
    Math.floor((Date.now() - new Date(value).getTime()) / 1000),
  );
  if (seconds < 10) return "Gerade eben";
  if (seconds < 60) return `Vor ${seconds} Sek.`;
  if (seconds < 3600) return `Vor ${Math.floor(seconds / 60)} Min.`;
  if (seconds < 86400) return `Vor ${Math.floor(seconds / 3600)} Std.`;
  return new Date(value).toLocaleDateString("de-DE");
};
const headers = (token: string): Record<string, string> =>
  token ? { "X-NCC-Dashboard-Token": token } : {};
async function getJson<T>(url: string, token: string): Promise<T> {
  const response = await fetch(url, { headers: headers(token) });
  if (!response.ok) {
    const error = new Error(
      response.status === 401 ? "AUTH" : "REQUEST",
    ) as Error & { status: number };
    error.status = response.status;
    throw error;
  }
  return response.json() as Promise<T>;
}
async function postJson<T>(
  url: string,
  token: string,
  body?: unknown,
): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    headers: { ...headers(token), "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const error = new Error("REQUEST") as Error & { status: number };
    error.status = response.status;
    throw error;
  }
  return response.json() as Promise<T>;
}

function Brand() {
  return (
    <div className="brand">
      <div className="brand-mark">
        <Signal size={22} />
      </div>
      <div>
        <strong>
          no<span>0</span>bz
        </strong>
        <small>COMMAND CENTER</small>
      </div>
    </div>
  );
}
function StatusDot({ online }: { online: boolean }) {
  return (
    <span className={`status-dot ${online ? "is-online" : "is-offline"}`}>
      <i />
      {online ? "ONLINE" : "OFFLINE"}
    </span>
  );
}

function StatCard({
  label,
  value,
  detail,
  icon,
  tone = "accent",
}: {
  label: string;
  value: string | number;
  detail: string;
  icon: React.ReactNode;
  tone?: string;
}) {
  return (
    <article className={`stat-card tone-${tone}`}>
      <div className="stat-icon">{icon}</div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{detail}</small>
      </div>
    </article>
  );
}

function Gauge({
  label,
  value,
  tone = "accent",
  detail,
  footer,
  children,
}: {
  label: string;
  value: number;
  tone?: string;
  detail: string;
  footer?: string;
  children?: React.ReactNode;
}) {
  const safe = Math.max(0, Math.min(100, value));
  return (
    <article className={`gauge-card tone-${tone}`}>
      <header>
        <span>{label}</span>
        <b>{detail}</b>
      </header>
      <div className="gauge">
        <svg viewBox="0 0 120 120">
          <circle cx="60" cy="60" r="48" className="gauge-track" />
          <circle
            cx="60"
            cy="60"
            r="48"
            className="gauge-value"
            strokeDasharray="301.6"
            strokeDashoffset={301.6 * (1 - safe / 100)}
          />
        </svg>
        <div>
          <strong>{safe.toFixed(1)}%</strong>
          <small>AUSLASTUNG</small>
        </div>
      </div>
      {footer && <footer className="gauge-footer">{footer}</footer>}
      {children}
    </article>
  );
}

function Sparkline({
  points,
  metric,
  color = "var(--accent)",
  maxValue = 100,
}: {
  points: Telemetry[];
  metric: (m: Metrics) => number;
  color?: string;
  maxValue?: number;
}) {
  const values = points.map((point) =>
    Math.max(0, Math.min(100, (metric(point.metrics) / Math.max(1, maxValue)) * 100)),
  );
  const line =
    values.length > 1
      ? values
          .map(
            (value, index) =>
              `${index ? "L" : "M"} ${(index / (values.length - 1)) * 100} ${100 - value}`,
          )
          .join(" ")
      : "";
  const gradient = `fill-${color.replace(/\W/g, "")}`;
  return (
    <div className="sparkline">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none">
        <defs>
          <linearGradient id={gradient} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor={color} stopOpacity=".35" />
            <stop offset="1" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        {line && (
          <>
            <path
              d={`${line} L 100 100 L 0 100 Z`}
              fill={`url(#${gradient})`}
            />
            <path
              d={line}
              fill="none"
              stroke={color}
              strokeWidth="1.7"
              vectorEffect="non-scaling-stroke"
            />
          </>
        )}
      </svg>
      {!line && <span>Noch nicht genug Messwerte</span>}
    </div>
  );
}

function AlertPanel({
  alerts,
  onDismiss,
}: {
  alerts: FleetAlert[];
  onDismiss: (id: string) => void;
}) {
  if (!alerts.length) return null;
  return (
    <section className="surface fleet-alerts">
      <header className="section-head">
        <div>
          <span className="eyebrow">AUFMERKSAMKEIT ERFORDERLICH</span>
          <h2>
            {alerts.length} aktuelle{" "}
            {alerts.length === 1 ? "Warnung" : "Warnungen"}
          </h2>
        </div>
        <AlertTriangle size={20} />
      </header>
      <div>
        {alerts.map((alert) => (
          <article key={alert.id} className={alert.severity}>
            <AlertTriangle size={16} />
            <div>
              <strong>{alert.title}</strong>
              <span>{alert.detail}</span>
            </div>
            <button
              type="button"
              className="alert-dismiss"
              title="Warnung ausblenden"
              aria-label={`${alert.title} ausblenden`}
              onClick={() => onDismiss(alert.id)}
            >
              <X size={15} />
            </button>
          </article>
        ))}
      </div>
    </section>
  );
}

function Fleet({
  nodes,
  groups,
  selected,
  points,
  monthlyNetwork,
  onSelect,
  query,
  onQuery,
  alerts,
  onCreateGroup,
  onLayout,
  canDelete,
  dismissedAlerts,
  onDismissAlert,
}: {
  nodes: Node[];
  groups: FleetGroup[];
  selected: Node | null;
  points: Telemetry[];
  monthlyNetwork: NetworkUsageSummary | null;
  onSelect: (id: string) => void;
  query: string;
  onQuery: (v: string) => void;
  alerts: AlertRecord[];
  onCreateGroup: (name: string) => Promise<void>;
  onLayout: (placements: FleetPlacement[]) => Promise<void>;
  canDelete: boolean;
  dismissedAlerts: Set<string>;
  onDismissAlert: (id: string) => void;
}) {
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({}),
    [editing, setEditing] = useState(false),
    [draggedNodeId, setDraggedNodeId] = useState<string | null>(null);
  const fleetAlerts: FleetAlert[] = alerts.filter((alert) => alert.active && !dismissedAlerts.has(alert.alert_id)).map((alert) => ({
    id: alert.alert_id, title: alert.message, detail: `${alert.display_name} · seit ${ago(alert.opened_at)}`, severity: alert.severity,
  }));
  const filtered = nodes.filter((node) =>
    `${node.display_name} ${node.platform} ${node.machine_id}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  const grouped = groups.map((group) => ({
    ...group,
    nodes: filtered.filter((node) => node.fleet_group_id === group.group_id).sort((left, right) => left.fleet_position - right.fleet_position || left.display_name.localeCompare(right.display_name, "de")),
  }));
  const fullGrouped = groups.map((group) => ({
    ...group,
    nodes: nodes.filter((node) => node.fleet_group_id === group.group_id).sort((left, right) => left.fleet_position - right.fleet_position || left.display_name.localeCompare(right.display_name, "de")),
  }));
  const moveNode = async (targetGroupId: string, beforeNodeId?: string) => {
    if (!draggedNodeId) return;
    const source = fullGrouped.find((group) => group.nodes.some((node) => node.node_id === draggedNodeId));
    const target = fullGrouped.find((group) => group.group_id === targetGroupId);
    if (!source || !target) return;
    const targetNodes = target.nodes.filter((node) => node.node_id !== draggedNodeId);
    const index = beforeNodeId ? Math.max(0, targetNodes.findIndex((node) => node.node_id === beforeNodeId)) : targetNodes.length;
    targetNodes.splice(index, 0, nodes.find((node) => node.node_id === draggedNodeId)!);
    const placements = [...new Set([source.group_id, targetGroupId])].flatMap((groupId) => {
      const groupNodes = groupId === targetGroupId ? targetNodes : source.nodes.filter((node) => node.node_id !== draggedNodeId);
      return groupNodes.map((node, position) => ({ node_id: node.node_id, group_id: groupId, position }));
    });
    setDraggedNodeId(null);
    await onLayout(placements);
  };
  return (
    <>
      <AlertPanel alerts={fleetAlerts} onDismiss={onDismissAlert} />
      <section className="surface fleet-navigator">
        <header>
          <div>
            <span className="eyebrow">FLEET NAVIGATOR</span>
            <strong>{nodes.filter((node) => node.online).length}/{nodes.length} SYSTEME AKTIV</strong>
          </div>
          <div className="navigator-actions">
            {editing && (
              <button
                type="button"
                onClick={() => {
                  const name = window.prompt("Name der neuen Gruppe");
                  if (name?.trim()) void onCreateGroup(name.trim());
                }}
              >
                + Gruppe
              </button>
            )}
            <button type="button" className={editing ? "active" : ""} onClick={() => setEditing((current) => !current)}>
              {editing ? "Fertig" : "Bearbeiten"}
            </button>
          </div>
          <label className="search">
            <Search size={15} />
            <input value={query} onChange={(event) => onQuery(event.target.value)} placeholder="Gerät suchen …" />
          </label>
        </header>
        <div className="navigator-groups">
          {grouped.map((group) => <section className="navigator-group" key={group.group_id}><button className="node-group-toggle" onClick={() => setCollapsedGroups((current) => ({...current, [group.group_id]: !current[group.group_id]}))}><h3>{group.name}<span>{group.nodes.length} · {collapsedGroups[group.group_id] ? "+" : "–"}</span></h3></button>{!collapsedGroups[group.group_id] && <div className={editing ? "editing" : ""} onDragOver={(event) => { if (editing) event.preventDefault(); }} onDrop={(event) => { if (editing) { event.preventDefault(); void moveNode(group.group_id); } }}>{group.nodes.map((node) => {
              return (
                <button
                  key={node.node_id}
                  className={`navigator-node ${selected?.node_id === node.node_id ? "selected" : ""}`}
                  draggable={editing}
                  onDragStart={() => setDraggedNodeId(node.node_id)}
                  onDragEnd={() => setDraggedNodeId(null)}
                  onDragOver={(event) => { if (editing) event.preventDefault(); }}
                  onDrop={(event) => { if (editing) { event.preventDefault(); event.stopPropagation(); void moveNode(group.group_id, node.node_id); } }}
                  onClick={() => { if (!editing) onSelect(node.node_id); }}
                >
                  <div className={`device-icon ${node.online ? "online" : ""}`}>
                    <Server size={17} />
                  </div>
                  <div className="node-copy">
                    <strong>{node.display_name}</strong>
                    <span>{node.platform} · {node.agent_version || "Agent unbekannt"}</span>
                    {node.access_role === "beta_tester" && <small className="fleet-beta-badge">BETA-TESTER</small>}
                  </div>
                  <StatusDot online={node.online} />
                </button>
              );
            })}{!group.nodes.length && <span className="navigator-placeholder">{editing ? "Gerät hierher ziehen" : "Platz für weitere Geräte"}</span>}</div>}</section>)}
            {!filtered.length && (
              <div className="navigator-empty">
                <Boxes size={30} />
                <strong>Keine Geräte gefunden</strong>
                <span>Starte einen NCC-Agenten oder ändere die Suche.</span>
              </div>
            )}
        </div>
      </section>
      <div className="fleet-stage">
        <NodeOverview node={selected} points={points} monthlyNetwork={monthlyNetwork} canDelete={canDelete} />
      </div>
    </>
  );
}

function UnraidStorageCard({ metrics }: { metrics: Metrics }) {
  const wanted = (metrics.disks || [])
    .filter((disk: Metrics) =>
      /^(cache|disk [1-4])$/i.test(String(disk.name || "")),
    )
    .sort((a: Metrics, b: Metrics) =>
      String(a.name).localeCompare(String(b.name), "de", { numeric: true }),
    );
  return (
    <article className="surface compact unraid-storage-card">
      <header>
        <HardDrive size={16} />
        <span>SPEICHERBELEGUNG</span>
      </header>
      <div className="unraid-storage-list">
        {wanted.map((disk: Metrics) => (
          <div key={String(disk.name)}>
            <div>
              <strong>{disk.name}</strong>
              <small>
                {num(disk.used_gb).toFixed(1)} / {num(disk.total_gb).toFixed(1)}{" "}
                GB
              </small>
            </div>
            <div className="storage-bar">
              <i style={{ width: `${num(disk.percent)}%` }} />
            </div>
            <b>{num(disk.percent).toFixed(0)}%</b>
            <em>
              {disk.spinning === false
                ? "Spindown"
                : typeof disk.temperature_c === "number"
                  ? `${num(disk.temperature_c).toFixed(0)} °C`
                  : "–"}
            </em>
          </div>
        ))}
        {!wanted.length && <p>Keine Cache- oder Disk-Daten verfügbar.</p>}
      </div>
    </article>
  );
}

function UnraidWorkloadCard({
  title,
  icon,
  items,
  kind,
}: {
  title: string;
  icon: React.ReactNode;
  items: Metrics[];
  kind: "vm" | "container";
}) {
  const running = (state: unknown) =>
    /running|started|up/i.test(String(state || ""));
  const ordered = [...items].sort((left, right) => {
    const activity = Number(running(right.state)) - Number(running(left.state));
    return activity || String(left.name || "").localeCompare(String(right.name || ""), "de");
  });
  return (
    <article className="surface compact unraid-workload-card">
      <header>
        {icon}
        <span>{title}</span>
        <b>{items.length}</b>
      </header>
      <div className="unraid-workload-list">
        {ordered.map((item, index) => (
          <div key={`${item.name}-${index}`}>
            <strong>{item.name || `Unbenannt ${kind}`}</strong>
            <span className={running(item.state) ? "running" : "stopped"}>
              {running(item.state)
                ? "LÄUFT"
                : String(item.state || "GESTOPPT").toUpperCase()}
            </span>
          </div>
        ))}
        {!items.length && (
          <p>Keine {kind === "vm" ? "VMs" : "Container"} vorhanden.</p>
        )}
      </div>
    </article>
  );
}

function NodeOverview({
  node,
  points,
  monthlyNetwork,
  canDelete,
}: {
  node: Node | null;
  points: Telemetry[];
  monthlyNetwork: NetworkUsageSummary | null;
  canDelete: boolean;
}) {
  const [forgetting, setForgetting] = useState(false),
    [renaming, setRenaming] = useState(false);
  if (!node)
    return (
      <section className="surface empty-stage">
        <Server size={45} />
        <h2>Noch kein Gerät verbunden</h2>
        <p>
          Sobald ein Agent Daten sendet, erscheint er automatisch in dieser
          Fleet.
        </p>
      </section>
    );
  const m = node.latest?.metrics || {},
    cpu = m.cpu || {},
    memory = m.memory || {},
    gpu = m.gpus?.[0] || {},
    network = m.network || {},
    processes = m.processes || [],
    isUnraid = node.metadata.source === "unraid-api";
  const forget = async () => {
    if (
      !window.confirm(
        `„${node.display_name}“ wirklich vergessen? Alle gespeicherten Messwerte und die zugehörigen Agent-Tokens werden entfernt.`,
      )
    )
      return;
    setForgetting(true);
    const dashboardToken = localStorage.getItem("ncc-dashboard-token") || "";
    const response = await fetch(`/api/v1/fleet/nodes/${node.node_id}`, {
      method: "DELETE",
      headers: headers(dashboardToken),
    });
    if (response.ok) {
      window.location.reload();
      return;
    }
    setForgetting(false);
    window.alert(
      "Das Gerät konnte nicht entfernt werden. Bitte erneut versuchen.",
    );
  };
  const rename = async () => {
    const displayName = window
      .prompt("Neuer Gerätename", node.display_name)
      ?.trim();
    if (!displayName || displayName === node.display_name) return;
    setRenaming(true);
    const dashboardToken = localStorage.getItem("ncc-dashboard-token") || "";
    const response = await fetch(`/api/v1/fleet/nodes/${node.node_id}`, {
      method: "PATCH",
      headers: {
        ...headers(dashboardToken),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ display_name: displayName }),
    });
    if (response.ok) {
      window.location.reload();
      return;
    }
    setRenaming(false);
    window.alert("Der Gerätename konnte nicht geändert werden.");
  };
  const cpuTemperature =
    typeof cpu.temperature_c === "number"
      ? `${num(cpu.temperature_c).toFixed(0)} °C CPU-Temperatur`
      : undefined;
  return (
    <section className="node-overview">
      <div className={`surface hero ${isUnraid ? "unraid-hero" : ""}`}>
        <div>
          <span className="eyebrow">
            {isUnraid ? "UNRAID STORAGE SERVER" : "AUSGEWÄHLTER NODE"}
          </span>
          <h1>{node.display_name}</h1>
          <p>
            {isUnraid
              ? `UNRAID API · ${node.machine_id}`
              : `${node.platform.toUpperCase()} · ${String(node.metadata.architecture || "Architektur unbekannt")} · ${node.machine_id}`}
          </p>
        </div>
        <div className="hero-status">
          <StatusDot online={node.online} />
          <small>{ago(node.last_seen_at)}</small>
        </div>
      </div>
      <div className={`gauge-grid ${isUnraid ? "unraid-gauge-grid" : ""}`}>
        <Gauge
          label="CPU AUSLASTUNG"
          value={num(cpu.percent)}
          detail={typeof cpu.frequency_mhz === "number" ? `${metric(cpu.frequency_mhz, 0)} MHz` : "CPU"}
        >
          {Array.isArray(cpu.per_core) && cpu.per_core.length > 0 && <div className="cpu-threads"><div><span>CORE THREADS ({num(cpu.logical_cores) || cpu.per_core.length})</span><b>AVG: {num(cpu.percent).toFixed(0)}%</b></div><section>{cpu.per_core.map((value: unknown, index: number) => { const load = Math.max(0, Math.min(100, num(value))); return <i key={index} title={`Kern ${index + 1}: ${load.toFixed(1)}%`} style={{ height: `${Math.max(12, load)}%`, backgroundColor: `hsl(${145 - load * 1.45} 88% 55%)` }} />; })}</section></div>}
        </Gauge>
        <Gauge
          label="ARBEITSSPEICHER"
          value={num(memory.percent)}
          tone="blue"
          detail={`${num(memory.used_gb).toFixed(1)} / ${num(memory.total_gb).toFixed(1)} GB`}
        />
        {!isUnraid && (
          <Gauge
            label="GPU"
            value={num(gpu.percent)}
            tone="purple"
            detail={gpu.name || "Nicht erkannt"}
            footer={
              typeof gpu.temperature_c === "number"
                ? `${metric(gpu.temperature_c, 0)} °C GPU-Temperatur`
                : undefined
            }
          />
        )}
      </div>
      <div className="detail-grid">
        <article className="surface compact">
          <header>
            <Network size={16} />
            <span>NETZWERK</span>
          </header>
          <div className="network-graphs" aria-label="Netzwerkverlauf">
            <div>
              <small>DOWNLOAD-VERLAUF <b>↓ {num(network.download_mbps).toFixed(1)} Mbps</b></small>
              <Sparkline
                points={points}
                metric={(point) => num(point.network?.download_mbps)}
                maxValue={Math.max(10, ...points.map((point) => num(point.metrics.network?.download_mbps)))}
                color="var(--blue)"
              />
            </div>
            <div>
              <small>UPLOAD-VERLAUF <b>↑ {num(network.upload_mbps).toFixed(1)} Mbps</b></small>
              <Sparkline
                points={points}
                metric={(point) => num(point.network?.upload_mbps)}
                maxValue={Math.max(10, ...points.map((point) => num(point.metrics.network?.upload_mbps)))}
                color="var(--purple)"
              />
            </div>
          </div>
          <footer>
            {network.interface || "Automatische Schnittstelle"} · {monthlyNetwork?.available
              ? `Monat ${new Date(monthlyNetwork.period_start).toLocaleDateString("de-DE", { month: "short" })}: ↓ ${metric(monthlyNetwork.received_bytes / 1024 ** 3, 2)} GB · ↑ ${metric(monthlyNetwork.sent_bytes / 1024 ** 3, 2)} GB`
              : "Monatsverkehr wird mit den nächsten Agent-Messungen erfasst"}
            {(num(network.errors) > 0 || num(network.drops) > 0) && ` · Fehler ${num(network.errors)} · Drops ${num(network.drops)}`}
          </footer>
        </article>
        {isUnraid ? (
          <UnraidStorageCard metrics={m} />
        ) : (
          <article className="surface compact">
            <header>
              <HardDrive size={16} />
              <span>LAUFWERKE</span>
            </header>
            <div className="disk-list">
              {(m.disks || [])
                .slice(0, 3)
                .map((disk: Metrics, index: number) => (
                  <article className="drive-card" key={`${disk.mount}-${index}`}>
                    <header>
                      <span><HardDrive size={15} />{disk.mount || disk.name || `Disk ${index + 1}`}</span>
                      <b>{Math.min(100, num(disk.percent)).toFixed(0)}%</b>
                    </header>
                    <small>{disk.name || disk.mount || `Disk ${index + 1}`} · {disk.filesystem || "Lokales Laufwerk"}</small>
                    <div className="drive-bar">
                      <i style={{ width: `${Math.min(100, num(disk.percent))}%` }} />
                    </div>
                    <div className="drive-capacity"><span>{metric(disk.used_gb, 0)} GB belegt</span><span>{Math.max(0, num(disk.total_gb) - num(disk.used_gb)).toFixed(0)} GB frei</span></div>
                    <div className="drive-rates">
                      <div><ArrowDownToLine size={14} /><span>LESEN</span><b>{metric(disk.read_mbps)} <small>MiB/s</small></b></div>
                      <div><ArrowUpToLine size={14} /><span>SCHREIBEN</span><b>{metric(disk.write_mbps)} <small>MiB/s</small></b></div>
                    </div>
                  </article>
                ))}
              {!(m.disks || []).length && <p>Keine Laufwerksdaten</p>}
            </div>
          </article>
        )}
      </div>
      {isUnraid && (
        <div className="unraid-services-grid">
          <UnraidWorkloadCard
            title="VIRTUAL MACHINES"
            icon={<MonitorCog size={16} />}
            items={m.vms || []}
            kind="vm"
          />
          <UnraidWorkloadCard
            title="DOCKER CONTAINER"
            icon={<Boxes size={16} />}
            items={m.containers || []}
            kind="container"
          />
        </div>
      )}
      {!isUnraid && (
        <div className="system-insights-grid">
          <article className="surface system-insight process-insight">
            <header><Activity size={16} /><span>AKTIVSTE PROZESSE</span></header>
            <div className="process-list">
              {processes.slice(0, 6).map((process: Metrics) => <div key={process.pid}><span title={process.name}>{process.name || "Unbekannt"}</span><b>CPU {Math.min(100, num(process.cpu)).toFixed(1)}%</b><small>RAM {metric(process.memory)}%</small><small>GPU {typeof m.process_gpu?.[String(process.pid)] === "number" ? `${Math.min(100, num(m.process_gpu[String(process.pid)])).toFixed(1)}%` : "—"}</small></div>)}
              {!processes.length && <p>Keine Prozessdaten verfügbar.</p>}
            </div>
          </article>
        </div>
      )}
      <div className="node-actions">
        <button
          className="rename-node"
          disabled={renaming}
          onClick={() => void rename()}
        >
          {renaming ? "Wird umbenannt …" : "Gerät umbenennen"}
        </button>
        {canDelete && <button
          className="forget-node"
          disabled={forgetting}
          onClick={() => void forget()}
        >
          <Trash2 size={15} />
          {forgetting ? "Gerät wird entfernt …" : "Gerät vergessen"}
        </button>}
      </div>
    </section>
  );
}

function StatisticsPage() {
  return (
    <section className="surface statistics-placeholder">
      <BarChart3 size={42} />
      <span className="eyebrow">NCC STATISTIKEN</span>
      <h1>Deine Daten bekommen ein Zuhause.</h1>
      <p>
        Monatsverkehr wird bereits dauerhaft aus den Rohdaten berechnet. Als
        Nächstes entstehen hier Zeiträume, Vergleiche und Langzeitverläufe für
        deine gesamte Fleet.
      </p>
      <div>
        <span>NETZWERK</span><span>RESSOURCEN</span><span>VERFÜGBARKEIT</span>
      </div>
    </section>
  );
}

function TelemetryPage({
  node,
  points,
}: {
  node: Node | null;
  points: Telemetry[];
}) {
  if (!node)
    return (
      <section className="surface empty-stage">
        <Activity size={44} />
        <h2>Keine Telemetrie verfügbar</h2>
      </section>
    );
  const latest = node.latest?.metrics || {},
    cpu = latest.cpu || {},
    memory = latest.memory || {},
    gpu = latest.gpus?.[0] || {},
    network = latest.network || {},
    diskUse = Math.max(0, ...(latest.disks || []).map((disk: Metrics) => num(disk.percent)));
  return (
    <div className="telemetry-page">
      <div className="surface telemetry-title">
        <div>
          <span className="eyebrow">LIVE TELEMETRIE</span>
          <h1>{node.display_name}</h1>
          <p>{points.length} Messpunkte im aktuellen Diagramm</p>
        </div>
        <StatusDot online={node.online} />
      </div>
      <div className="chart-grid">
        <article className="surface chart-card">
          <header>
            <div className="chart-icon red">
              <Cpu size={17} />
            </div>
            <div>
              <span>CPU-LAST</span>
              <strong>{num(cpu.percent).toFixed(1)}%</strong>
            </div>
          </header>
          <Sparkline points={points} metric={(m) => num(m.cpu?.percent)} />
        </article>
        <article className="surface chart-card">
          <header>
            <div className="chart-icon blue">
              <MemoryStick size={17} />
            </div>
            <div>
              <span>RAM-AUSLASTUNG</span>
              <strong>{num(memory.percent).toFixed(1)}%</strong>
            </div>
          </header>
          <Sparkline
            points={points}
            metric={(m) => num(m.memory?.percent)}
            color="var(--blue)"
          />
        </article>
        <article className="surface chart-card">
          <header><div className="chart-icon blue"><Network size={17} /></div><div><span>NETZWERK · DOWNLOAD</span><strong>{num(network.download_mbps).toFixed(1)} Mbps</strong></div></header>
          <Sparkline points={points} metric={(m) => num(m.network?.download_mbps)} maxValue={Math.max(10, ...points.map((point) => num(point.metrics.network?.download_mbps)))} color="var(--blue)" />
        </article>
        <article className="surface chart-card">
          <header><div className="chart-icon purple"><Network size={17} /></div><div><span>NETZWERK · UPLOAD</span><strong>{num(network.upload_mbps).toFixed(1)} Mbps</strong></div></header>
          <Sparkline points={points} metric={(m) => num(m.network?.upload_mbps)} maxValue={Math.max(10, ...points.map((point) => num(point.metrics.network?.upload_mbps)))} color="var(--purple)" />
        </article>
        <article className="surface chart-card">
          <header><div className="chart-icon blue"><HardDrive size={17} /></div><div><span>HÖCHSTE LAUFWERKBELEGUNG</span><strong>{diskUse.toFixed(1)}%</strong></div></header>
          <Sparkline points={points} metric={(m) => Math.max(0, ...(m.disks || []).map((disk: Metrics) => num(disk.percent)))} color="var(--blue)" />
        </article>
        {typeof cpu.temperature_c === "number" && <article className="surface chart-card">
          <header><div className="chart-icon red"><Cpu size={17} /></div><div><span>CPU-TEMPERATUR</span><strong>{num(cpu.temperature_c).toFixed(0)} °C</strong></div></header>
          <Sparkline points={points} metric={(m) => num(m.cpu?.temperature_c)} color="var(--amber)" />
        </article>}
        <article className="surface chart-card">
          <header>
            <div className="chart-icon purple">
              <MonitorCog size={17} />
            </div>
            <div>
              <span>GPU-LAST</span>
              <strong>{num(gpu.percent).toFixed(1)}%</strong>
            </div>
          </header>
          <Sparkline
            points={points}
            metric={(m) => num(m.gpus?.[0]?.percent)}
            color="var(--purple)"
          />
        </article>
      </div>
      <section className="surface metadata">
        <header className="section-head">
          <div>
            <span className="eyebrow">NODE INFORMATION</span>
            <h2>Systemdetails</h2>
          </div>
        </header>
        <dl>
          <dt>Geräte-ID</dt>
          <dd>{node.machine_id}</dd>
          <dt>Plattform</dt>
          <dd>{node.platform}</dd>
          <dt>Agent-Version</dt>
          <dd>{node.agent_version || "Unbekannt"}</dd>
          <dt>Erster Kontakt</dt>
          <dd>{new Date(node.created_at).toLocaleString("de-DE")}</dd>
          <dt>Letzter Kontakt</dt>
          <dd>
            {node.last_seen_at
              ? new Date(node.last_seen_at).toLocaleString("de-DE")
              : "Noch nie"}
          </dd>
          <dt>Status</dt>
          <dd>
            <StatusDot online={node.online} />
          </dd>
        </dl>
      </section>
    </div>
  );
}

function AlertsPage({ alerts }: { alerts: AlertRecord[] }) {
  const active = alerts.filter((alert) => alert.active);
  return (
    <section className="alerts-page">
      <div className="surface alerts-title">
        <div>
          <span className="eyebrow">FLEET-WARNUNGEN</span>
          <h1>Warnungszentrum</h1>
          <p>
            {active.length
              ? `${active.length} aktive ${active.length === 1 ? "Warnung" : "Warnungen"}`
              : "Keine aktive Warnung"}
          </p>
        </div>
        <Bell size={25} />
      </div>
      <div className="alert-records">
        {alerts.map((alert) => (
          <article
            key={alert.alert_id}
            className={`surface ${alert.active ? alert.severity : "resolved"}`}
          >
            <AlertTriangle size={18} />
            <div>
              <strong>
                {alert.active ? alert.message : `Entwarnt: ${alert.message}`}
              </strong>
              <span>
                {alert.display_name} · {alert.kind.toUpperCase()} ·{" "}
                {alert.active
                  ? `seit ${new Date(alert.opened_at).toLocaleString("de-DE")}`
                  : `behoben ${new Date(alert.resolved_at || alert.updated_at).toLocaleString("de-DE")}`}
              </span>
            </div>
            <b>
              {alert.active
                ? alert.severity === "critical"
                  ? "KRITISCH"
                  : "WARNUNG"
                : "BEHOBEN"}
            </b>
          </article>
        ))}
        {!alerts.length && (
          <div className="surface empty-stage">
            <Bell size={42} />
            <h2>Alles ruhig</h2>
            <p>
              Aktive und behobene NCC-Warnungen erscheinen hier automatisch.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}

function SettingsPage({
  theme,
  onTheme,
  onToken,
  policy,
  onPolicy,
}: {
  theme: Theme;
  onTheme: (v: Theme) => void;
  onToken: () => void;
  policy: AlertPolicy | null;
  onPolicy: (policy: AlertPolicy) => Promise<void>;
}) {
  const [draft, setDraft] = useState<AlertPolicy | null>(policy);
  useEffect(() => setDraft(policy), [policy]);
  return (
    <div className="settings-page">
      <section className="surface settings-card">
        <header className="section-head">
          <div>
            <span className="eyebrow">DARSTELLUNG</span>
            <h2>Theme auswählen</h2>
          </div>
          <Moon size={19} />
        </header>
        <div className="theme-grid">
          {THEMES.map((item) => (
            <button
              key={item.id}
              className={theme === item.id ? "active" : ""}
              onClick={() => onTheme(item.id)}
            >
              <i style={{ background: item.color }} />
              <span>{item.name}</span>
              {theme === item.id && <Check size={15} />}
            </button>
          ))}
        </div>
      </section>
      <section className="surface settings-card">
        <header className="section-head">
          <div>
            <span className="eyebrow">WARNUNGEN</span>
            <h2>Grenzwerte</h2>
          </div>
          <Bell size={19} />
        </header>
        <p>Telegram und Dashboard warnen ab dem gewählten Wert.</p>
        {draft && (
          <form
            className="alert-policy"
            onSubmit={(event) => {
              event.preventDefault();
              void onPolicy(draft);
            }}
          >
            {(
              [
                "cpu_threshold",
                "memory_threshold",
                "gpu_threshold",
                "disk_threshold",
              ] as const
            ).map((key) => (
              <label key={key}>
                {key.replace("_threshold", "").toUpperCase()}
                <input
                  type="number"
                  min="50"
                  max="100"
                  value={draft[key]}
                  onChange={(event) =>
                    setDraft({ ...draft, [key]: Number(event.target.value) })
                  }
                />
                <span>%</span>
              </label>
            ))}
            <button className="primary" type="submit">
              Grenzwerte speichern
            </button>
          </form>
        )}
      </section>
      <section className="surface settings-card">
        <header className="section-head">
          <div>
            <span className="eyebrow">SICHERHEIT</span>
            <h2>Dashboard-Zugang</h2>
          </div>
          <ShieldCheck size={19} />
        </header>
        <p>
          Der Dashboard-Token ist vom Agent-Token getrennt und bleibt
          ausschließlich in diesem Browser gespeichert.
        </p>
        <button className="primary" onClick={onToken}>
          <KeyRound size={16} /> Dashboard-Token ändern
        </button>
      </section>
    </div>
  );
}

function EnrollmentPage({
  invitations,
  onCreate,
  onRevoke,
  busy,
  canManageAccess,
}: {
  invitations: Invitation[];
  onCreate: (name: string, hours: number) => Promise<IssuedInvitation>;
  onRevoke: (id: string) => Promise<void>;
  busy: boolean;
  canManageAccess: boolean;
}) {
  const [name, setName] = useState(""),
    [hours, setHours] = useState("168"),
    [platform, setPlatform] = useState<"windows" | "linux">("linux"),
    [issued, setIssued] = useState<IssuedInvitation | null>(null),
    [error, setError] = useState(""),
    [codeLabel, setCodeLabel] = useState(""),
    [betaTester, setBetaTester] = useState(false),
    [adminCode, setAdminCode] = useState<IssuedAdminCode | null>(null),
    [adminCodes, setAdminCodes] = useState<AdminCode[]>([]),
    [pairings, setPairings] = useState<AgentPairing[]>([]);
  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      setIssued(await onCreate(name, Number(hours)));
    } catch {
      setError(
        "Die Einladung konnte nicht erstellt werden. Bitte erneut versuchen.",
      );
    }
  };
  const copy = async (value: string, label: string) => {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      setError(
        `${label} konnte nicht automatisch kopiert werden. Bitte manuell kopieren.`,
      );
    }
  };
  const loadAdminCodes = async () => {
    try {
      setAdminCodes(
        await getJson<AdminCode[]>(
          "/api/v1/admin-codes",
          localStorage.getItem("ncc-dashboard-token") || "",
        ),
      );
    } catch {
      setAdminCodes([]);
    }
  };
  useEffect(() => {
    void loadAdminCodes();
  }, []);
  const loadPairings = async () => {
    try {
      setPairings(
        await getJson<AgentPairing[]>(
          "/api/v1/agent-pairings",
          localStorage.getItem("ncc-dashboard-token") || "",
        ),
      );
    } catch {
      setPairings([]);
    }
  };
  useEffect(() => {
    void loadPairings();
    const timer = window.setInterval(() => void loadPairings(), 5000);
    return () => clearInterval(timer);
  }, []);
  const createAdminCode = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      setAdminCode(
        await postJson<IssuedAdminCode>(
          "/api/v1/admin-codes",
          localStorage.getItem("ncc-dashboard-token") || "",
          { label: codeLabel, expires_minutes: 15, beta_tester: betaTester },
        ),
      );
      setCodeLabel("");
      setBetaTester(false);
      void loadAdminCodes();
    } catch {
      setError(
        "Der Admin-Code konnte nicht erstellt werden. Bitte erneut versuchen.",
      );
    }
  };
  const revokeAdminCode = async (id: string) => {
    try {
      await postJson<AdminCode>(
        `/api/v1/admin-codes/${id}/revoke`,
        localStorage.getItem("ncc-dashboard-token") || "",
      );
      void loadAdminCodes();
    } catch {
      setError(
        "Der Zugang konnte nicht widerrufen werden. Bitte erneut versuchen.",
      );
    }
  };
  const expires = (item: Invitation) =>
    item.expires_at
      ? new Date(item.expires_at).toLocaleString("de-DE")
      : "Läuft nicht ab";
  const server = window.location.hostname;
  const command =
    platform === "linux"
      ? `cd ~/ncc && sudo ./scripts/install_ncc_agent_service.sh --tailscale ${server}`
      : `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\install_ncc_service.ps1 -Component Agent -Tailscale -ServerUrl ${server}`;
  const platformName = platform === "linux" ? "Linux / CachyOS" : "Windows";
  return (
    <div className="enrollment-page">
      <section className="surface enrollment-intro">
        <div>
          <span className="eyebrow">GERÄT AUFNEHMEN</span>
          <h1>Agent-Einladung erstellen</h1>
          <p>
            Erstelle einen Token, wähle das Zielsystem und folge den drei klaren
            Schritten. Der Klartext wird nur einmal angezeigt; der Server
            speichert ausschließlich einen sicheren Prüfwert.
          </p>
        </div>
        <UserPlus size={28} />
      </section>
      {canManageAccess && <div className="enrollment-grid">
        <section className="surface enrollment-form">
          <header className="section-head">
            <div>
              <span className="eyebrow">NEUE EINLADUNG</span>
              <h2>Gerät vorbereiten</h2>
            </div>
          </header>
          <form onSubmit={create}>
            <label>
              Gerätename
              <input
                required
                maxLength={128}
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="z. B. CachyOS Laptop"
              />
            </label>
            <label>
              Zielsystem
              <select
                value={platform}
                onChange={(event) =>
                  setPlatform(event.target.value as "windows" | "linux")
                }
              >
                <option value="linux">Linux / CachyOS</option>
                <option value="windows">Windows</option>
              </select>
            </label>
            <label>
              Gültigkeit
              <select
                value={hours}
                onChange={(event) => setHours(event.target.value)}
              >
                <option value="24">24 Stunden</option>
                <option value="168">7 Tage</option>
                <option value="720">30 Tage</option>
                <option value="0">Läuft nicht ab</option>
              </select>
            </label>
            {error && <small className="form-error">{error}</small>}
            <button className="primary" disabled={busy} type="submit">
              <KeyRound size={16} /> Einladung erzeugen
            </button>
          </form>
        </section>
        {issued ? (
          <section className="surface token-reveal">
            <span className="eyebrow">SCHRITT 1 · NUR JETZT SICHTBAR</span>
            <h2>
              {platformName} für {issued.name} einrichten
            </h2>
            <p>
              Erst den Token kopieren. Auf dem Zielgerät wird er anschließend
              verdeckt abgefragt.
            </p>
            <div>
              <code>{issued.token}</code>
              <button
                onClick={() => void copy(issued.token, "Der Token")}
                aria-label="Token kopieren"
              >
                <Copy size={17} />
              </button>
            </div>
            <div className="setup-step">
              <span>SCHRITT 2 · AUF DEM ZIELGERÄT AUSFÜHREN</span>
              <div>
                <code>{command}</code>
                <button
                  onClick={() => void copy(command, "Der Installationsbefehl")}
                  aria-label="Installationsbefehl kopieren"
                >
                  <Copy size={17} />
                </button>
              </div>
            </div>
            <ol className="setup-guide">
              <li>
                Im NCC-Projektordner ausführen. Unter Linux liegt er
                normalerweise in <code>~/ncc</code>.
              </li>
              <li>
                Administratorfreigabe bestätigen und den kopierten Agent-Token
                einfügen. Die Eingabe bleibt unsichtbar.
              </li>
              <li>
                Der Dienst startet automatisch; das Gerät erscheint kurz darauf
                in der Fleet.
              </li>
            </ol>
            <small>
              Der Token ist nicht Bestandteil des Befehls und bleibt somit aus
              der Shell-Historie heraus.
            </small>
          </section>
        ) : (
          <section className="surface enrollment-help">
            <KeyRound size={27} />
            <h2>So funktioniert es</h2>
            <ol>
              <li>Gerät und Zielsystem wählen.</li>
              <li>Einladungstoken einmalig kopieren.</li>
              <li>
                Passenden Befehl auf dem Zielgerät ausführen und Token verdeckt
                einfügen.
              </li>
            </ol>
          </section>
        )}
      </div>}
      {canManageAccess && <><section className="surface invitation-list">
        <header className="section-head">
          <div>
            <span className="eyebrow">BROWSER-ZUGANG</span>
            <h2>Admin-Code erstellen</h2>
          </div>
          <ShieldCheck size={19} />
        </header>
        <p>
          Der achtstellige Code gewährt auf einem neuen Browser vollständigen
          Dashboard-Zugang. Er ist nur einmal und 15 Minuten lang gültig.
        </p>
        <form onSubmit={createAdminCode}>
          <label>
            Für welches Gerät oder welche Person?
            <input
              required
              maxLength={128}
              value={codeLabel}
              onChange={(event) => setCodeLabel(event.target.value)}
              placeholder="z. B. Pixel 7 Pro"
            />
          </label>
          <label className="beta-tester-toggle">
            <input
              type="checkbox"
              checked={betaTester}
              onChange={(event) => setBetaTester(event.target.checked)}
            />
            <span>
              <strong>Beta-Tester</strong>
              <small>Kein Erstellen neuer Codes und keine Löschrechte.</small>
            </span>
          </label>
          <button className="primary" disabled={busy} type="submit">
            <KeyRound size={16} /> Admin-Code erzeugen
          </button>
        </form>
        {adminCode && (
          <div className="setup-step">
            <span>
              NUR JETZT SICHTBAR · GÜLTIG BIS{" "}
              {new Date(adminCode.expires_at).toLocaleTimeString("de-DE")}
            </span>
            <div>
              <code>{adminCode.code}</code>
              <button
                onClick={() => void copy(adminCode.code, "Der Admin-Code")}
                aria-label="Admin-Code kopieren"
              >
                <Copy size={17} />
              </button>
            </div>
            <small>
              Auf dem Zielgerät die Dashboard-Adresse öffnen und diesen Code
              eingeben. {adminCode.access_role === "beta_tester" ? "Der Zugang ist als Beta-Tester eingeschränkt." : "Der Zugang ist Commander."}
            </small>
          </div>
        )}
        <div className="invitation-rows">
          {adminCodes.map((item) => (
            <article key={item.code_id}>
              <div>
                <strong>{item.label}</strong>
                <span>
                  Erstellt: {new Date(item.created_at).toLocaleString("de-DE")}{" "}
                  · Läuft ab:{" "}
                  {new Date(item.expires_at).toLocaleString("de-DE")}
                </span>
                {item.access_role === "beta_tester" && <small className="beta-badge">BETA-TESTER</small>}
              </div>
              <span className={`invitation-status ${item.status}`}>
                {item.status === "ready"
                  ? "Bereit"
                  : item.status === "used"
                    ? "Verwendet"
                    : item.status === "expired"
                      ? "Abgelaufen"
                      : "Widerrufen"}
              </span>
              {item.status !== "revoked" && (
                <button
                  onClick={() => void revokeAdminCode(item.code_id)}
                  disabled={busy}
                  title="Zugang widerrufen"
                >
                  <Ban size={15} />
                </button>
              )}
            </article>
          ))}
          {!adminCodes.length && (
            <div className="empty">
              <ShieldCheck size={30} />
              <strong>Noch keine Admin-Codes</strong>
              <span>Erstelle einen Code für einen weiteren Browser.</span>
            </div>
          )}
        </div>
      </section>
      <section className="surface invitation-list">
        <header className="section-head">
          <div>
            <span className="eyebrow">GERÄTE-PAIRING</span>
            <h2>Neue Geräte</h2>
          </div>
          <UserPlus size={19} />
        </header>
        <p>
          Nach der Installation erscheint ein Gerät hier automatisch. Öffne den
          angezeigten Pairing-Link auf dem Zielgerät und melde dich dort mit
          einem Admin-Code an.
        </p>
        <div className="invitation-rows">
          {pairings.slice(0, 8).map((item) => (
            <article key={item.pairing_id}>
              <div>
                <strong>{item.display_name}</strong>
                <span>
                  {item.platform} · Angefragt:{" "}
                  {new Date(item.created_at).toLocaleString("de-DE")}
                </span>
              </div>
              <span className={`invitation-status ${item.status}`}>
                {item.status === "waiting"
                  ? "Wartet"
                  : item.status === "approved"
                    ? "Freigegeben"
                    : item.status === "claimed"
                      ? "Verbunden"
                      : item.status === "expired"
                        ? "Abgelaufen"
                        : "Abgebrochen"}
              </span>
            </article>
          ))}
          {!pairings.length && (
            <div className="empty">
              <UserPlus size={30} />
              <strong>Keine offenen Geräte</strong>
              <span>
                Installiere den Agenten auf einem weiteren PC oder Server.
              </span>
            </div>
          )}
        </div>
      </section>
      <section className="surface invitation-list">
        <header className="section-head">
          <div>
            <span className="eyebrow">EINLADUNGEN</span>
            <h2>Token-Verwaltung</h2>
          </div>
          <b>
            {invitations.filter((item) => item.status === "ready").length} AKTIV
          </b>
        </header>
        <div className="invitation-rows">
          {invitations.map((item) => (
            <article key={item.token_id}>
              <div>
                <strong>{item.name}</strong>
                <span>
                  Erstellt: {new Date(item.created_at).toLocaleString("de-DE")}{" "}
                  · {expires(item)}
                </span>
                {item.node_name && (
                  <small>Verbunden mit: {item.node_name}</small>
                )}
              </div>
              <span className={`invitation-status ${item.status}`}>
                {item.status === "ready"
                  ? "Bereit"
                  : item.status === "bound"
                    ? "Gebunden"
                    : item.status === "expired"
                      ? "Abgelaufen"
                      : "Widerrufen"}
              </span>
              {(item.status === "ready" || item.status === "bound") && (
                <button
                  onClick={() => void onRevoke(item.token_id)}
                  disabled={busy}
                  title="Einladung widerrufen"
                >
                  <Ban size={15} />
                </button>
              )}
            </article>
          ))}
          {!invitations.length && (
            <div className="empty">
              <UserPlus size={30} />
              <strong>Noch keine Einladungen</strong>
              <span>Erstelle den ersten Token für ein weiteres Gerät.</span>
            </div>
          )}
        </div>
      </section></>}
    </div>
  );
}

function Login({
  onSave,
  error,
}: {
  onSave: (value: string) => void;
  error: boolean;
}) {
  const [value, setValue] = useState(""),
    [localError, setLocalError] = useState(false);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLocalError(false);
    const code = value.trim().toUpperCase();
    if (/^[A-Z0-9]{8}$/.test(code)) {
      try {
        const response = await fetch("/api/v1/admin-codes/redeem", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code }),
        });
        if (!response.ok) throw new Error("CODE");
        localStorage.removeItem("ncc-dashboard-token");
        onSave("");
      } catch {
        setLocalError(true);
      }
      return;
    }
    onSave(value);
  };
  return (
    <div className="login">
      <div className="login-glow" />
      <section>
        <Brand />
        <div className="login-icon">
          <KeyRound size={26} />
        </div>
        <span className="eyebrow">GESCHÜTZTER ZUGANG</span>
        <h1>Willkommen, Commander.</h1>
        <p>
          Gib deinen achtstelligen Admin-Code ein. Er wird im Dashboard erzeugt
          und gewährt vollständigen Admin-Zugang.
        </p>
        <form onSubmit={(event) => void submit(event)}>
          <label>
            Admin-Code
            <input
              autoFocus
              value={value}
              onChange={(e) => setValue(e.target.value.toUpperCase())}
              autoCapitalize="characters"
              autoComplete="one-time-code"
              placeholder="z. B. AB12CD34"
            />
          </label>
          {(error || localError) && (
            <small className="form-error">
              Der Code wurde nicht akzeptiert oder ist abgelaufen.
            </small>
          )}
          <button className="primary" type="submit">
            <ShieldCheck size={17} /> Verbindung herstellen
          </button>
        </form>
        <details>
          <summary>Bestehenden Zugang übertragen</summary>
          <p>
            Nur während der Umstellung kann hier weiterhin der bisherige
            Dashboard-Token eingegeben werden.
          </p>
        </details>
      </section>
    </div>
  );
}

function App() {
  const [theme, setTheme] = useState<Theme>(
    () => (localStorage.getItem("ncc-fleet-theme") as Theme) || "nightmare",
  );
  const [token, setToken] = useState(
    () => localStorage.getItem("ncc-dashboard-token") || "",
  );
  const [authenticated, setAuthenticated] = useState<boolean | null>(null),
    [authError, setAuthError] = useState(false);
  const [nodes, setNodes] = useState<Node[]>([]),
    [groups, setGroups] = useState<FleetGroup[]>([]),
    [summary, setSummary] = useState<Summary | null>(null),
    [invitations, setInvitations] = useState<Invitation[]>([]),
    [alerts, setAlerts] = useState<AlertRecord[]>([]),
    [policy, setPolicy] = useState<AlertPolicy | null>(null),
    [selectedId, setSelectedId] = useState(""),
    [points, setPoints] = useState<Telemetry[]>([]),
    [monthlyNetwork, setMonthlyNetwork] = useState<NetworkUsageSummary | null>(null);
  const [dismissedAlertIds, setDismissedAlertIds] = useState<Set<string>>(
    () => new Set(JSON.parse(localStorage.getItem("ncc-dismissed-alerts") || "[]")),
  );
  const [accessRole, setAccessRole] = useState<AccessRole>("commander");
  const [page, setPage] = useState<Page>("fleet"),
    [query, setQuery] = useState(""),
    [loading, setLoading] = useState(true),
    [sidebar, setSidebar] = useState(false),
    [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem("ncc-sidebar-collapsed") === "true"),
    [clock, setClock] = useState(new Date());
  const selected =
    nodes.find((node) => node.node_id === selectedId) || nodes[0] || null;
  const load = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true);
      try {
        const [
          nextNodes,
          nextGroups,
          nextSummary,
          nextInvitations,
          nextAlerts,
          nextPolicy,
          nextAccess,
        ] = await Promise.all([
          getJson<Node[]>("/api/v1/fleet/nodes", token),
          getJson<FleetGroup[]>("/api/v1/fleet/groups", token),
          getJson<Summary>("/api/v1/fleet/summary", token),
          getJson<Invitation[]>("/api/v1/agent-invitations", token),
          getJson<AlertRecord[]>("/api/v1/fleet/alerts", token),
          getJson<AlertPolicy>("/api/v1/fleet/alert-policy", token),
          getJson<DashboardAccess>("/api/v1/admin-codes/access", token),
        ]);
        setNodes(nextNodes);
        setGroups(nextGroups);
        setSummary(nextSummary);
        setInvitations(nextInvitations);
        setAlerts(nextAlerts);
        const activeAlertIds = new Set(
          nextAlerts.filter((alert) => alert.active).map((alert) => alert.alert_id),
        );
        setDismissedAlertIds((current) => {
          const next = new Set([...current].filter((id) => activeAlertIds.has(id)));
          if (next.size === current.size && [...next].every((id) => current.has(id))) return current;
          localStorage.setItem("ncc-dismissed-alerts", JSON.stringify([...next]));
          return next;
        });
        setPolicy(nextPolicy);
        setAccessRole(nextAccess.access_role);
        setAuthenticated(true);
        setAuthError(false);
        setSelectedId((current) =>
          nextNodes.some((node) => node.node_id === current)
            ? current
            : nextNodes[0]?.node_id || "",
        );
      } catch (error) {
        if ((error as Error & { status?: number }).status === 401) {
          setAuthenticated(false);
          setAuthError(true);
        }
      } finally {
        setLoading(false);
      }
    },
    [token],
  );
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("ncc-fleet-theme", theme);
  }, [theme]);
  useEffect(() => localStorage.setItem("ncc-sidebar-collapsed", String(sidebarCollapsed)), [sidebarCollapsed]);
  useEffect(() => {
    void load();
    const poll = window.setInterval(() => void load(true), 5000);
    return () => clearInterval(poll);
  }, [load]);
  useEffect(() => {
    const timer = window.setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    if (!selected) return;
    getJson<Telemetry[]>(
      `/api/v1/fleet/nodes/${selected.node_id}/telemetry?limit=120`,
      token,
    )
      .then(setPoints)
      .catch(() => setPoints([]));
  }, [selected?.node_id, selected?.latest?.recorded_at, token]);
  useEffect(() => {
    if (!selected) return;
    getJson<NetworkUsageSummary>(
      `/api/v1/fleet/nodes/${selected.node_id}/network/month`,
      token,
    )
      .then(setMonthlyNetwork)
      .catch(() => setMonthlyNetwork(null));
  }, [selected?.node_id, selected?.latest?.recorded_at, token]);
  useEffect(() => {
    const pairingId = new URLSearchParams(window.location.search).get("pair");
    if (authenticated !== true || !pairingId) return;
    postJson(
      `/api/v1/agent-pairings/${encodeURIComponent(pairingId)}/approve`,
      token,
    )
      .then(() => window.history.replaceState({}, "", window.location.pathname))
      .catch(() => undefined);
  }, [authenticated, token]);
  const saveToken = (value: string) => {
    localStorage.setItem("ncc-dashboard-token", value);
    setToken(value);
    setAuthenticated(null);
    setAuthError(false);
  };
  const dismissAlert = (id: string) => {
    setDismissedAlertIds((current) => {
      const next = new Set(current);
      next.add(id);
      localStorage.setItem("ncc-dismissed-alerts", JSON.stringify([...next]));
      return next;
    });
  };
  const createInvitation = async (name: string, hours: number) => {
    const created = await postJson<IssuedInvitation>(
      "/api/v1/agent-invitations",
      token,
      { name, expires_hours: hours },
    );
    const { token: _, ...stored } = created;
    setInvitations((current) => [stored, ...current]);
    return created;
  };
  const revokeInvitation = async (id: string) => {
    await postJson<Invitation>(`/api/v1/agent-invitations/${id}/revoke`, token);
    const response = await fetch(`/api/v1/agent-invitations/${id}`, {
      method: "DELETE",
      headers: headers(token),
    });
    if (!response.ok) throw new Error("REQUEST");
    setInvitations((current) => current.filter((item) => item.token_id !== id));
  };
  const savePolicy = async (nextPolicy: AlertPolicy) => {
    const response = await fetch("/api/v1/fleet/alert-policy", {
      method: "PUT",
      headers: { ...headers(token), "Content-Type": "application/json" },
      body: JSON.stringify(nextPolicy),
    });
    if (!response.ok) throw new Error("REQUEST");
    setPolicy((await response.json()) as AlertPolicy);
  };
  const createFleetGroup = async (name: string) => {
    const group = await postJson<FleetGroup>("/api/v1/fleet/groups", token, { name });
    setGroups((current) => [...current, group].sort((left, right) => left.position - right.position || left.name.localeCompare(right.name, "de")));
  };
  const saveFleetLayout = async (placements: FleetPlacement[]) => {
    const response = await fetch("/api/v1/fleet/layout", {
      method: "PUT",
      headers: { ...headers(token), "Content-Type": "application/json" },
      body: JSON.stringify({ placements }),
    });
    if (!response.ok) throw new Error("REQUEST");
    const byNode = new Map(placements.map((placement) => [placement.node_id, placement]));
    setNodes((current) => current.map((node) => {
      const placement = byNode.get(node.node_id);
      return placement ? { ...node, fleet_group_id: placement.group_id, fleet_position: placement.position } : node;
    }));
  };
  const nav = useMemo(
    () => [
      {
        id: "fleet" as Page,
        label: "Fleet Übersicht",
        icon: <LayoutDashboard size={17} />,
      },
      {
        id: "statistics" as Page,
        label: "Statistiken",
        icon: <BarChart3 size={17} />,
      },
      { id: "alerts" as Page, label: "Warnungen", icon: <Bell size={17} /> },
      {
        id: "onboarding" as Page,
        label: "Gerät hinzufügen",
        icon: <UserPlus size={17} />,
      },
      {
        id: "settings" as Page,
        label: "Einstellungen",
        icon: <Settings size={17} />,
      },
    ],
    [],
  );
  const canManageAccess = accessRole === "commander";
  const visibleNav = canManageAccess ? nav : nav.filter((item) => item.id !== "onboarding");
  if (authenticated !== true)
    return (
      <Login onSave={saveToken} error={authenticated === false && authError} />
    );
  const title =
    page === "fleet"
      ? "Fleet Command"
      : page === "statistics"
        ? "Statistiken"
        : page === "alerts"
          ? "Warnungszentrum"
          : page === "onboarding"
            ? "Gerät hinzufügen"
            : "System Settings";
  return (
    <div className={`shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      <aside className={`${sidebar ? "open" : ""} ${sidebarCollapsed ? "collapsed" : ""}`}>
        <div className="aside-top">
          <Brand />
          <button className="sidebar-toggle" onClick={() => setSidebarCollapsed((current) => !current)} aria-label={sidebarCollapsed ? "Seitenmenü ausklappen" : "Seitenmenü einklappen"}>
            <ChevronRight size={18} />
          </button>
          <button className="close-menu" onClick={() => setSidebar(false)}>
            <X size={19} />
          </button>
        </div>
        <nav>
          <span>COMMAND CENTER</span>
          {visibleNav.map((item) => (
            <button
              key={item.id}
              className={page === item.id ? "active" : ""}
              onClick={() => {
                setPage(item.id);
                setSidebar(false);
              }}
            >
              {item.icon}
              <b>{item.label}</b>
              {page === item.id && <i />}
            </button>
          ))}
        </nav>
        <div className="server-health">
          <header>
            <span>SERVER STATUS</span>
            <b>
              <i /> BEREIT
            </b>
          </header>
          <dl>
            <dt>Nodes online</dt>
            <dd>{summary?.online_nodes || 0}</dd>
            <dt>Nodes offline</dt>
            <dd>{summary?.offline_nodes || 0}</dd>
            <dt>Messpunkte</dt>
            <dd>{summary?.telemetry_points.toLocaleString("de-DE") || 0}</dd>
            <dt>API</dt>
            <dd>v1</dd>
          </dl>
        </div>
        <footer>
          <ShieldCheck size={14} />
          <span>GESICHERTE VERBINDUNG</span>
          <b>v0.5.0-beta.40</b>
        </footer>
      </aside>
      <div className="mobile-scrim" onClick={() => setSidebar(false)} />
      <div className="content">
        <header className="topbar">
          <button className="menu" onClick={() => setSidebar(true)}>
            <Menu size={20} />
          </button>
          <div>
            <span className="eyebrow">NO0BZ INFRASTRUCTURE</span>
            <strong>{title}</strong>
          </div>
          <div className="top-actions">
            <div className="clock">
              <Clock3 size={14} />
              <span>{clock.toLocaleTimeString("de-DE")}</span>
            </div>
            <button
              aria-label="Warnungszentrum"
              onClick={() => setPage("alerts")}
            >
              <Bell size={17} />
              {alerts.some((alert) => alert.active) && <i />}
            </button>
            <button
              className="refresh"
              onClick={() => void load()}
              aria-label="Aktualisieren"
            >
              <RefreshCw size={17} className={loading ? "spin" : ""} />
            </button>
            <div className="commander">
              <span>{canManageAccess ? "C" : "B"}</span>
              <div>
                <b>{canManageAccess ? "Commander" : "Beta-Tester"}</b>
                <small className={canManageAccess ? "" : "beta-badge"}>{canManageAccess ? "Administrator" : "BETA-TESTER"}</small>
              </div>
            </div>
          </div>
        </header>
        <main>
          {page === "fleet" ? (
            <Fleet
              nodes={nodes}
              groups={groups}
              selected={selected}
              onSelect={setSelectedId}
              points={points}
              monthlyNetwork={monthlyNetwork}
              query={query}
              onQuery={setQuery}
              alerts={alerts}
              onCreateGroup={createFleetGroup}
              onLayout={saveFleetLayout}
              canDelete={canManageAccess}
              dismissedAlerts={dismissedAlertIds}
              onDismissAlert={dismissAlert}
            />
          ) : page === "statistics" ? (
            <StatisticsPage />
          ) : page === "alerts" ? (
            <AlertsPage alerts={alerts} />
          ) : page === "onboarding" ? (
            <EnrollmentPage
              invitations={invitations}
              onCreate={createInvitation}
              onRevoke={revokeInvitation}
              busy={loading}
              canManageAccess={canManageAccess}
            />
          ) : (
            <SettingsPage
              theme={theme}
              onTheme={setTheme}
              onToken={() => setAuthenticated(false)}
              policy={policy}
              onPolicy={savePolicy}
            />
          )}
        </main>
        <footer className="statusbar">
          <span>
            <i /> NCC SERVER VERBUNDEN
          </span>
          <b>
            {selected
              ? `${selected.display_name} · ${ago(selected.last_seen_at)}`
              : "WARTE AUF AGENTEN"}
          </b>
          <span>{clock.toLocaleDateString("de-DE")}</span>
        </footer>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
