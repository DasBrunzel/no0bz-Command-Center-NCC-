import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
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
  Download,
  FileText,
  Gamepad2,
  HardDrive,
  KeyRound,
  LayoutDashboard,
  Image as ImageIcon,
  MemoryStick,
  Maximize2,
  Menu,
  MessageSquare,
  MonitorCog,
  Moon,
  Network,
  Film,
  Music2,
  RefreshCw,
  Paperclip,
  Search,
  Server,
  Send,
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
import "./concept/styles.css";
import "./design.css";
import { Icon as ConceptIcon, Meter as ConceptMeter, SectionHead as ConceptSectionHead, Sparkline as ConceptSparkline, Status as ConceptStatus } from "./concept/components";
import { HardwareSensorsCard } from "./HardwareSensors";
import { activeGamingUntil, NowPlayingCard, NowPlayingStrip, PlaytimeStatistics, type GameTracking, type NowPlaying } from "./Games";
import dashboardPackage from "../package.json";

const Markdown = React.lazy(() => import("react-markdown"));
const DASHBOARD_VERSION = dashboardPackage.version;

type Metrics = Record<string, any>;
type Telemetry = {
  point_id: string;
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
  availability_percent: number;
  availability_started_at: string | null;
  uptime_record_seconds: number;
  gaming_mode_until: string | null;
  auto_gaming_until?: string | null;
  auto_gaming_mode?: boolean;
  game_tracking?: GameTracking;
  now_playing?: NowPlaying | null;
  fleet_group_id: string;
  fleet_position: number;
  physical_device_id: string | null;
  physical_device_name: string | null;
  update_channel: "beta" | "stable";
  pending_release_id: string | null;
  update_check_requested_at?: string | null;
  latest: Telemetry | null;
};
type AgentRelease = {
  release_id: string;
  payload_version: string;
  channel: "beta" | "stable";
  platform: "windows" | "linux";
  architecture: string;
  artifact_url: string;
  sha256: string;
  size_bytes: number;
  signature_key_id: string;
  signature_value: string;
  minimum_core_version: string | null;
  released_at: string;
  assigned_nodes: number;
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
type NetworkHistorySample = { recorded_at: string; network: Metrics | null };
type Theme = "system" | "light" | "dark";
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
type ServerVersion = { version: string; api: string };
type DashboardUser = { user_id: string | null; username: string; role: AccessRole; active: boolean; managed: boolean; created_at?: string | null };
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
type TelegramSettings = {
  configured: boolean;
  enabled: boolean;
  warning_title: string;
  critical_title: string;
  resolved_title: string;
  footer: string;
};
type ChatAttachment = { name: string; content_type: string; size: number; url: string };
type ChatMessage = { message_id: string; sender_node_id: string | null; sender_user_id: string | null; sender_name: string; body: string; body_format: "plain" | "markdown"; attachment: ChatAttachment | null; created_at: string };
type ChatParticipant = { user_id: string | null; display_name: string; role: AccessRole };
type Page = "fleet" | "explorer" | "statistics" | "alerts" | "chat" | "onboarding" | "settings";

const THEMES: { id: Theme; name: string }[] = [
  { id: "system", name: "Wie das System" },
  { id: "light", name: "Hell" },
  { id: "dark", name: "Dunkel" },
];
const num = (value: unknown) =>
  typeof value === "number" && Number.isFinite(value) ? value : 0;
const metric = (value: unknown, digits = 1) =>
  typeof value === "number" && Number.isFinite(value)
    ? value.toFixed(digits)
    : "—";
const trafficBytes = (value: unknown) => {
  let amount = Math.max(0, num(value));
  if (amount < 1024) return `${Math.round(amount)} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let unit = 0;
  amount /= 1024;
  while (amount >= 1024 && unit < units.length - 1) { amount /= 1024; unit++; }
  return `${amount.toLocaleString("de-DE", { maximumFractionDigits: amount < 10 ? 2 : amount < 100 ? 1 : 0 })} ${units[unit]}`;
};
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
const duration = (value: number) => {
  const seconds = Math.max(0, Math.floor(value));
  if (seconds < 60) return "unter 1 Min.";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days) return `${days} T ${hours} Std.`;
  if (hours) return `${hours} Std. ${minutes} Min.`;
  return `${minutes} Min.`;
};
const headers = (token: string): Record<string, string> =>
  token ? { "X-NCC-Dashboard-Token": token } : {};
async function getJson<T>(url: string, token: string, timeoutMs = 20_000): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { headers: headers(token), signal: controller.signal });
    if (!response.ok) {
      const error = new Error(
        response.status === 401 ? "AUTH" : "REQUEST",
      ) as Error & { status: number };
      error.status = response.status;
      throw error;
    }
    return await response.json() as T;
  } finally {
    window.clearTimeout(timeout);
  }
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
        <small>Command Center</small>
      </div>
    </div>
  );
}
function StatusDot({ online }: { online: boolean }) {
  return (
    <span className={`status-dot ${online ? "is-online" : "is-offline"}`}>
      <i />
      {online ? "Online" : "Offline"}
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
          <small>Auslastung</small>
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

function TrafficHistoryChart({ values }: { values: { download: number; upload: number }[] }) {
  const maximum = Math.max(1, ...values.flatMap((value) => [value.download, value.upload]));
  const line = (metric: "download" | "upload") => values.length > 1
    ? values.map((value, index) => {
      const x = (index / (values.length - 1)) * 100;
      const y = 100 - (Math.max(0, value[metric]) / maximum) * 90 - 5;
      return `${index ? "L" : "M"}${x.toFixed(2)} ${y.toFixed(2)}`;
    }).join(" ")
    : "";
  return (
    <div className="statistics-live-chart">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Live-Netzwerkverkehr">
        <path className="grid" d="M0 25H100M0 50H100M0 75H100" />
        {line("download") && <path className="download" d={line("download")} />}
        {line("upload") && <path className="upload" d={line("upload")} />}
      </svg>
      {!line("download") && <span>Live-Verlauf wird aufgebaut …</span>}
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
          <span className="eyebrow">Aufmerksamkeit erforderlich</span>
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
  onAttachProfile,
  onDetachProfile,
  canDelete,
  releases,
  token,
  dismissedAlerts,
  onDismissAlert,
  onAddDevice,
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
  onAttachProfile: (deviceId: string, nodeId: string) => Promise<void>;
  onDetachProfile: (deviceId: string, nodeId: string) => Promise<void>;
  canDelete: boolean;
  releases: AgentRelease[];
  token: string;
  dismissedAlerts: Set<string>;
  onDismissAlert: (id: string) => void;
  onAddDevice: () => void;
}) {
  const [navigatorCollapsed, setNavigatorCollapsed] = useState(false),
    [editing, setEditing] = useState(false),
    [draggedNodeId, setDraggedNodeId] = useState<string | null>(null);
  const [groupFilter, setGroupFilter] = useState("Alle Gruppen");
  const [statusFilter, setStatusFilter] = useState("Alle Status");
  const [sortFilter, setSortFilter] = useState("name");
  const [linkTarget, setLinkTarget] = useState("");
  const [linkBusy, setLinkBusy] = useState(false);
  const [linkError, setLinkError] = useState("");
  useEffect(() => { setLinkTarget(""); setLinkError(""); }, [selected?.node_id]);
  const physicalDevices = Array.from(nodes.reduce((result, node) => {
    if (node.physical_device_id && !result.has(node.physical_device_id)) {
      result.set(node.physical_device_id, node.physical_device_name || node.display_name);
    }
    return result;
  }, new Map<string, string>()));
  const selectedProfiles = selected?.physical_device_id
    ? nodes.filter((node) => node.physical_device_id === selected.physical_device_id)
    : [];
  const changeProfileLink = async (attach: boolean) => {
    if (!selected) return;
    const deviceId = attach ? linkTarget : selected.physical_device_id;
    if (!deviceId) return;
    setLinkBusy(true);
    setLinkError("");
    try {
      if (attach) await onAttachProfile(deviceId, selected.node_id);
      else await onDetachProfile(deviceId, selected.node_id);
      setLinkTarget("");
    } catch { setLinkError("Das OS-Profil konnte nicht zugeordnet werden. Bitte erneut versuchen."); }
    finally { setLinkBusy(false); }
  };
  const fleetAlerts: FleetAlert[] = alerts.filter((alert) => alert.active && !dismissedAlerts.has(alert.alert_id)).map((alert) => ({
    id: alert.alert_id, title: alert.message, detail: `${alert.display_name} · seit ${ago(alert.opened_at)}`, severity: alert.severity,
  }));
  const filtered = nodes.filter((node) =>
    `${node.display_name} ${node.platform} ${node.machine_id}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  const representativeNodes = (source: Node[]) => Array.from(source.reduce((result, node) => {
    const key = node.physical_device_id || node.node_id;
    const current = result.get(key);
    // A dualboot machine appears once. Prefer the currently running OS.
    if (!current || (node.online && !current.online)) result.set(key, node);
    return result;
  }, new Map<string, Node>()).values());
  const grouped = groups.map((group) => ({
    ...group,
    nodes: representativeNodes(filtered.filter((node) => node.fleet_group_id === group.group_id)).sort((left, right) => left.fleet_position - right.fleet_position || left.display_name.localeCompare(right.display_name, "de")),
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
  const visibleNodes = representativeNodes(filtered).filter((node) =>
    (groupFilter === "Alle Gruppen" || groups.find((group) => group.group_id === node.fleet_group_id)?.name === groupFilter) &&
    (statusFilter === "Alle Status" ||
      (statusFilter === "Online" && node.online) ||
      (statusFilter === "Offline" && !node.online) ||
      (statusFilter === "Gaming Mode" && !!activeGamingUntil(node))),
  ).sort((left, right) => sortFilter === "cpu"
    ? num(right.latest?.metrics.cpu?.percent) - num(left.latest?.metrics.cpu?.percent)
    : sortFilter === "group"
      ? String(groups.find((group) => group.group_id === left.fleet_group_id)?.name || "").localeCompare(String(groups.find((group) => group.group_id === right.fleet_group_id)?.name || ""), "de")
      : left.display_name.localeCompare(right.display_name, "de"));
  return <>
    <div className="page-intro"><div><div className="eyebrow">FLEET / EXPLORER</div><h1>Deine Fleet.</h1><p>Physische Geräte, Profile und Zustände an einem Ort.</p></div><button type="button" className="primary-button" onClick={onAddDevice}><ConceptIcon name="plus" size={17}/> Gerät hinzufügen</button></div>
    <div className="summary-line"><span><b>{new Set(nodes.map((node) => node.physical_device_id || node.node_id)).size}</b> physische Geräte</span><span><b>{nodes.length}</b> OS-Profile</span><span><b>{nodes.filter((node) => node.online).length}</b> verbunden</span><span><b>{nodes.filter((node) => activeGamingUntil(node)).length}</b> Gaming Mode</span></div>
    <div className="filter-bar"><label className="search-box"><ConceptIcon name="search" size={17}/><input value={query} onChange={(event) => onQuery(event.target.value)} placeholder="Gerät oder Plattform suchen…"/></label><select value={groupFilter} onChange={(event) => setGroupFilter(event.target.value)}><option>Alle Gruppen</option>{groups.map((group) => <option key={group.group_id}>{group.name}</option>)}</select><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>{["Alle Status", "Online", "Offline", "Gaming Mode"].map((status) => <option key={status}>{status}</option>)}</select><select value={sortFilter} onChange={(event) => setSortFilter(event.target.value)}><option value="name">Name A–Z</option><option value="cpu">CPU-Last</option><option value="group">Gruppe</option></select></div>
    <div className="fleet-list"><div className="table-heading"><span>Gerät / Plattform</span><span>Status</span><span>CPU / RAM</span><span>Letzter Kontakt</span><span/></div>{visibleNodes.length ? visibleNodes.map((node) => {
      const cpu = num(node.latest?.metrics.cpu?.percent), ram = num(node.latest?.metrics.memory?.percent);
      const profiles = nodes.filter((profile) => (profile.physical_device_id || profile.node_id) === (node.physical_device_id || node.node_id));
      return <button type="button" className={`fleet-item ${selected?.node_id === node.node_id ? "selected" : ""}`} key={node.node_id} onClick={() => onSelect(node.node_id)}><div className="fleet-identity"><div className="fleet-icon">{node.platform.toLowerCase().includes("linux") ? "▤" : "▣"}</div><div><b>{node.physical_device_name || node.display_name}</b><small>{node.platform} · {groups.find((group) => group.group_id === node.fleet_group_id)?.name || "Fleet"}</small>{profiles.length > 1 && <span className="profile-count">{profiles.length} OS-PROFILE <span>Dualboot</span></span>}</div></div><ConceptStatus node={{online: node.online, gaming_mode_until: activeGamingUntil(node)}}/><div className="fleet-meters"><div><span>CPU</span><ConceptMeter value={cpu}/><b>{cpu.toFixed(0)}%</b></div><div><span>RAM</span><ConceptMeter value={ram} color="var(--blue)"/><b>{ram.toFixed(0)}%</b></div></div><span className="last-seen">{node.online ? "Gerade eben" : ago(node.last_seen_at)}</span><ConceptIcon name="chevron" size={18}/></button>;
    }) : <div className="empty">Keine Geräte entsprechen diesen Filtern.</div>}</div>
    <div className="concept-fleet-actions"><button type="button" className="outline-button" onClick={() => setEditing((value) => !value)}>{editing ? "Gruppen schließen" : "Gruppen bearbeiten"}</button>{editing && <button type="button" className="outline-button" onClick={() => { const name = window.prompt("Name der neuen Gruppe"); if (name?.trim()) void onCreateGroup(name.trim()); }}>+ Gruppe</button>}</div>
    {editing && <div className="concept-group-editor">{grouped.map((group) => <div key={group.group_id} className="detail-card" onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); void moveNode(group.group_id); }}><strong>{group.name}</strong>{group.nodes.map((node) => <button type="button" key={node.node_id} draggable onDragStart={() => setDraggedNodeId(node.node_id)} onDragEnd={() => setDraggedNodeId(null)} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); event.stopPropagation(); void moveNode(group.group_id, node.node_id); }}>{node.display_name}</button>)}</div>)}</div>}
    {selected && <div className="concept-selected-node">
      <NodeOverview node={selected} points={points} monthlyNetwork={monthlyNetwork} canDelete={canDelete} releases={releases} token={token}/>
      {(selectedProfiles.length > 1 || canDelete) && <section className="concept-profile-link">
        <div><span className="eyebrow">OS-Profile</span><h3>Physisches Gerät</h3></div>
        {selectedProfiles.length > 1 && <div className="concept-profile-tabs">{selectedProfiles.map((profile) => <button type="button" className={profile.node_id === selected.node_id ? "active" : ""} key={profile.node_id} onClick={() => onSelect(profile.node_id)}>{profile.platform} · {profile.online ? "Online" : "Offline"}</button>)}</div>}
        {canDelete && (selected.physical_device_id
          ? <button type="button" className="outline-button" disabled={linkBusy} onClick={() => void changeProfileLink(false)}>Profil vom Gerät lösen</button>
          : <div className="concept-profile-attach"><label>Diesem Gerät zuordnen<select value={linkTarget} onChange={(event) => setLinkTarget(event.target.value)}><option value="">Physisches Gerät wählen</option>{physicalDevices.map(([id, name]) => <option value={id} key={id}>{name}</option>)}</select></label><button type="button" className="outline-button" disabled={!linkTarget || linkBusy} onClick={() => void changeProfileLink(true)}>Profil verknüpfen</button></div>)}
        {linkError && <small role="alert" className="form-error">{linkError}</small>}
      </section>}
    </div>}
  </>;
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
        <span>Speicherbelegung</span>
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
                ? "Läuft"
                : String(item.state || "Gestoppt")}
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

/** The overview uses the original markup and CSS from the approved local demo. */
function CommandOverviewExact({
  nodes, selected, points, alerts, dismissedAlerts, onSelect, onOpenAlerts, onOpenExplorer, token,
}: {
  token: string;
  nodes: Node[];
  selected: Node | null;
  points: Telemetry[];
  alerts: AlertRecord[];
  dismissedAlerts: Set<string>;
  onSelect: (nodeId: string) => void;
  onOpenAlerts: () => void;
  onOpenExplorer: () => void;
}) {
  const active = alerts.filter((alert) => alert.active && !dismissedAlerts.has(alert.alert_id));
  const representatives = Array.from(nodes.reduce((result, node) => {
    const key = node.physical_device_id || node.node_id;
    const current = result.get(key);
    if (!current || (node.online && !current.online)) result.set(key, node);
    return result;
  }, new Map<string, Node>()).values());
  const online = representatives.filter((node) => node.online).length;
  const offline = representatives.length - online;
  // The chart below uses the selected node's samples. Its headline values
  // must use that same node instead of an unrelated fleet-wide sum.
  const selectedNetwork = selected?.online ? selected.latest?.metrics.network : null;
  const down = num(selectedNetwork?.download_mbps);
  const up = num(selectedNetwork?.upload_mbps);
  const netHistory = selected?.online
    ? points.map((point) => num(point.metrics.network?.download_mbps))
    : [];
  const availability = representatives.length
    ? representatives.reduce((total, node) => total + num(node.availability_percent), 0) / representatives.length
    : 0;
  const events = active.length
    ? active.slice(0, 5).map((alert) => ({
        label: `${alert.display_name}: ${alert.message}`,
        when: ago(alert.updated_at),
        hot: alert.severity === "critical",
      }))
    : representatives.filter((node) => node.online).slice(0, 5).map((node) => ({
        label: `${node.display_name} meldet sich`, when: ago(node.last_seen_at), hot: false,
      }));
  const showNode = (node: Node) => { onSelect(node.node_id); onOpenExplorer(); };
  return <>
    <div className="page-intro">
      <div>
        <div className="eyebrow">{new Date().toLocaleDateString("de-DE", { weekday: "long", day: "2-digit", month: "long", year: "numeric" }).toUpperCase()}</div>
        <h1>Alles im Blick.</h1>
        <p>Deine Infrastruktur in Echtzeit. Ruhig, bis etwas deine Aufmerksamkeit braucht.</p>
      </div>
      <div className="freshness"><span className="pulse-dot"/> Daten frisch <b>·</b> {selected?.last_seen_at ? `Aktualisiert ${ago(selected.last_seen_at)}` : "Warte auf Telemetrie"}</div>
    </div>
    <NowPlayingStrip nodes={nodes} token={token} onOpen={(nodeId) => { onSelect(nodeId); onOpenExplorer(); }}/>
    <div className="hero-grid">
      <div className="attention-card">
        <div className="attention-top"><span className="eyebrow">Wichtig</span><span className={`severity ${active.length ? "critical" : "info"}`}>● {active.length ? `${active.length} aktiv` : "Stabil"}</span></div>
        <div className="attention-body"><div className="attention-icon"><ConceptIcon name={active.length ? "alert" : "check"} size={26}/></div><div><h2>{active.length ? "Was braucht gerade Aufmerksamkeit?" : "Alles läuft nach Plan."}</h2><p>{active[0]?.message || "Keine aktiven Vorfälle"}</p><small>{active.length ? `${active[0].display_name} · ${ago(active[0].updated_at)}` : "Alle erreichbaren Geräte senden aktuelle Telemetrie."}</small></div></div>
        <button className="text-link" onClick={onOpenAlerts}>Warnungen prüfen <ConceptIcon name="arrow" size={16}/></button>
      </div>
      <div className="system-card">
        <div className="eyebrow">Systemstatus</div>
        <div className="system-big">{representatives.length}<span> Geräte</span></div>
        <div className="system-bar"><span style={{width:`${representatives.length ? online / representatives.length * 100 : 0}%`}}/></div>
        <div className="system-legend"><span><i className="legend-online"/> {online} Online</span><span><i className="legend-warn"/> {active.length} Warnung</span><span><i className="legend-offline"/> {offline} Offline</span></div>
        <div className="system-foot">Erreichbarkeit <b>{offline ? "Eingeschränkt" : "Stabil"}</b></div>
      </div>
    </div>
    <div className="overview-main">
      <div className="overview-left">
        <div className="traffic-card">
          <div className="card-head"><div><div className="eyebrow">Netzwerk</div><h2>Netzwerkverkehr</h2></div><span className="live-tag"><i/> Live</span></div>
          <div className="traffic-values"><div><small>Download</small><strong>{down.toFixed(1)} <span>Mb/s</span></strong></div><div><small>Upload</small><strong>{up.toFixed(1)} <span>Mb/s</span></strong></div></div>
          <div className="traffic-chart"><div className="chart-grid"><span>{Math.ceil(Math.max(1, ...netHistory))}</span><span>{Math.ceil(Math.max(1, ...netHistory) / 2)}</span><span>0</span></div><ConceptSparkline values={netHistory} color="var(--mint)" height={188} fill/></div>
          <div className="chart-axis"><span>Verlauf: {selected?.display_name || "Kein Gerät"}</span><span>Letzte Messpunkte</span><span>Jetzt</span></div>
        </div>
        <div className="fleet-strip">
          <ConceptSectionHead eyebrow="Geräte" title="Geräte im Fokus" aside={<button className="text-link" onClick={onOpenExplorer}>Alle Geräte <ConceptIcon name="arrow" size={15}/></button>}/>
          <div className="node-rows">{representatives.slice(0, 5).map((node) => <button className="node-row" key={node.node_id} onClick={() => showNode(node)}>
            <div className="node-symbol">{node.fleet_group_id === "default-servers" ? "▤" : "▣"}</div>
            <div className="node-row-name"><b>{node.physical_device_name || node.display_name}</b><small>{node.platform}</small></div>
            <span className={`status ${node.online ? "online" : "offline"}`}><i/>{node.online ? "Online" : "Offline"}</span>
            <div className="row-load"><span>CPU {num(node.latest?.metrics.cpu?.percent).toFixed(0)}%</span><ConceptMeter value={num(node.latest?.metrics.cpu?.percent)}/></div>
            <ConceptIcon name="chevron" size={16}/>
          </button>)}</div>
        </div>
      </div>
      <div className="overview-right">
        <div className="event-card"><ConceptSectionHead eyebrow="Ereignisse" title="Ereignis-Zeitstrahl"/><div className="timeline">{events.map((event, index) => <div className="timeline-item" key={`${event.label}-${index}`}><span className={`timeline-dot ${event.hot ? "hot" : ""}`}/><div><b>{event.label}</b><small>{event.when}</small></div></div>)}</div><button className="text-link" onClick={onOpenAlerts}>Alle Warnungen <ConceptIcon name="arrow" size={15}/></button></div>
        <div className="signal-card"><div className="eyebrow">Verfügbarkeit</div><div className="signal-score">{availability.toFixed(1)}<span>%</span></div><p>Fleet-Verfügbarkeit · seit Aufnahme</p><div className="signal-bars" role="img" aria-label={`Fleet-Verfügbarkeit ${availability.toFixed(1)} Prozent`}>{Array.from({length:28},(_,i)=><span key={i} style={{height: i < Math.round(availability / 100 * 28) ? "100%" : "20%", opacity: i < Math.round(availability / 100 * 28) ? 0.65 : 0.18}}/>)}</div><small>Alle Knoten werden überwacht</small></div>
      </div>
    </div>
  </>;
}

function DashboardTrafficChart({ values }: { values: { download: number; upload: number }[] }) {
  const chart = values.length > 1 ? values : Array.from({ length: 18 }, () => ({ download: 0, upload: 0 }));
  const max = Math.max(1, ...chart.flatMap((value) => [value.download, value.upload]));
  const path = (key: "download" | "upload") => chart.map((value, index) => {
    const x = (index / Math.max(1, chart.length - 1)) * 100;
    const y = 89 - (value[key] / max) * 68;
    return `${index ? "L" : "M"}${x.toFixed(2)} ${y.toFixed(2)}`;
  }).join(" ");
  const download = path("download");
  return <div className="nccv3-traffic-chart"><svg viewBox="0 0 100 100" preserveAspectRatio="none"><defs><linearGradient id="nccv3-download" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#74dbc1" stopOpacity=".28" /><stop offset="1" stopColor="#74dbc1" stopOpacity="0" /></linearGradient></defs><path className="grid" d="M0 20H100M0 45H100M0 70H100M0 90H100" /><path d={`${download} L100 90 L0 90 Z`} fill="url(#nccv3-download)" /><path className="download" d={download} /><path className="upload" d={path("upload")} /></svg></div>;
}

function NodeOverview({
  node,
  points,
  monthlyNetwork,
  canDelete,
  releases,
  token,
}: {
  node: Node | null;
  points: Telemetry[];
  monthlyNetwork: NetworkUsageSummary | null;
  canDelete: boolean;
  releases: AgentRelease[];
  token: string;
}) {
  const [actionOpen, setActionOpen] = useState(false);
  const [forgetting, setForgetting] = useState(false),
    [renaming, setRenaming] = useState(false),
    [updatingRole, setUpdatingRole] = useState(false),
    [updatingGaming, setUpdatingGaming] = useState(false),
    [updatingRelease, setUpdatingRelease] = useState(false);
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
    lhmGpu = m.lhm_gpus?.[0] || {},
    network = m.network || {},
    isUnraid = node.metadata.source === "unraid-api";
  const gamingActive = !!activeGamingUntil(node);
  const updateGamingMode = async (minutes: number) => {
    setUpdatingGaming(true);
    const dashboardToken = localStorage.getItem("ncc-dashboard-token") || "";
    const response = await fetch(`/api/v1/fleet/nodes/${node.node_id}/gaming-mode`, {
      method: "PUT", headers: { ...headers(dashboardToken), "Content-Type": "application/json" }, body: JSON.stringify({ minutes }),
    });
    if (response.ok) { window.location.reload(); return; }
    setUpdatingGaming(false);
    window.alert("Der Gaming-Modus konnte nicht geändert werden.");
  };
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
    let detail = "";
    try {
      const body = (await response.json()) as { detail?: unknown };
      detail = typeof body.detail === "string" ? body.detail : "";
    } catch { /* Empty or non-JSON error responses use the status below. */ }
    window.alert(`Das Gerät konnte nicht entfernt werden (${response.status})${detail ? `: ${detail}` : "."}`);
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
  const toggleRole = async () => {
    const nextRole: AccessRole =
      node.access_role === "beta_tester" ? "commander" : "beta_tester";
    const label = nextRole === "beta_tester" ? "Beta-Tester" : "Commander";
    if (!window.confirm(`„${node.display_name}“ als ${label} markieren?`)) return;
    setUpdatingRole(true);
    const dashboardToken = localStorage.getItem("ncc-dashboard-token") || "";
    const response = await fetch(`/api/v1/fleet/nodes/${node.node_id}/role`, {
      method: "PATCH",
      headers: {
        ...headers(dashboardToken),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ access_role: nextRole }),
    });
    if (response.ok) {
      window.location.reload();
      return;
    }
    setUpdatingRole(false);
    window.alert("Die Geräte-Rolle konnte nicht geändert werden.");
  };
  const compatibleReleases = releases.filter((release) => release.platform === node.platform);
  const channelReleases = compatibleReleases.filter((release) => release.channel === node.update_channel);
  const pendingRelease = releases.find((release) => release.release_id === node.pending_release_id) || null;
  const setRelease = async (releaseId: string | null) => {
    setUpdatingRelease(true);
    const response = await fetch(`/api/v1/fleet/nodes/${node.node_id}/release`, {
      method: "PUT", headers: { ...headers(token), "Content-Type": "application/json" }, body: JSON.stringify({ release_id: releaseId }),
    });
    if (response.ok) { window.location.reload(); return; }
    setUpdatingRelease(false);
    window.alert("Update-Freigabe konnte nicht geändert werden.");
  };
  const assignRelease = () => {
    if (!channelReleases.length && !pendingRelease) {
      window.alert(`Für ${node.platform} im ${node.update_channel.toUpperCase()}-Kanal ist noch kein Release registriert.`);
      return;
    }
    if (pendingRelease) {
      if (window.confirm(`Freigabe für ${pendingRelease.payload_version} zurücknehmen?`)) void setRelease(null);
      return;
    }
    if (channelReleases.length === 1) void setRelease(channelReleases[0].release_id);
  };
  const [updateCheckState, setUpdateCheckState] = useState<"idle" | "sending" | "requested">(
    node.update_check_requested_at ? "requested" : "idle",
  );
  useEffect(() => {
    // The server clears the request once the agent's next heartbeat picked it up.
    if (!node.update_check_requested_at) setUpdateCheckState((state) => (state === "requested" ? "idle" : state));
  }, [node.update_check_requested_at]);
  const requestUpdateCheck = async () => {
    setUpdateCheckState("sending");
    try {
      await postJson(`/api/v1/fleet/nodes/${node.node_id}/update-check`, token);
      setUpdateCheckState("requested");
    } catch {
      setUpdateCheckState("idle");
      window.alert("Die Update-Prüfung konnte nicht angefordert werden.");
    }
  };
  const changeUpdateChannel = async () => {
    const channel = node.update_channel === "beta" ? "stable" : "beta";
    setUpdatingRelease(true);
    const response = await fetch(`/api/v1/fleet/nodes/${node.node_id}/update-channel`, {
      method: "PUT", headers: { ...headers(token), "Content-Type": "application/json" }, body: JSON.stringify({ channel }),
    });
    if (response.ok) { window.location.reload(); return; }
    setUpdatingRelease(false);
    window.alert("Update-Kanal konnte nicht geändert werden.");
  };
  const cpuTemperature =
    typeof cpu.temperature_c === "number"
      ? `${num(cpu.temperature_c).toFixed(0)} °C CPU-Temperatur`
      : undefined;
  const cpuModel = String(cpu.model || "CPU nicht erkannt");
  const gpuModel = String(gpu.name || gpu.model || "Keine GPU erkannt");
  const cpuLogo = (() => {
    const model = cpuModel.toLowerCase();
    if (model.includes("intel")) return "/assets/hardware/intel.svg";
    const ryzen = model.match(/ryzen\s*([3579])/i)?.[1];
    return ryzen ? `/assets/hardware/ryzen${ryzen}.jpg` : null;
  })();
  const gpuLogo = (() => {
    const model = gpuModel.toLowerCase();
    if (model.includes("nvidia") || model.includes("geforce"))
      return model.includes("rtx") ? "/assets/hardware/nvidia-rtx.jpg" : "/assets/hardware/nvidia-gtx.png";
    if (model.includes("amd") || model.includes("radeon")) return "/assets/hardware/amd-radeon.png";
    return null;
  })();
  const operatingSystem = isUnraid
    ? `Unraid ${m.unraid?.version || node.agent_version || ""}`.trim()
    : String(m.system?.platform || node.platform || "Betriebssystem unbekannt");
  const cpuSeries = points.map((point) => num(point.metrics.cpu?.percent));
  const gpuSeries = points.map((point) => num(point.metrics.gpus?.[0]?.percent));
  const downSeries = points.map((point) => num(point.metrics.network?.download_mbps));
  const storage = Array.isArray(m.disks) ? m.disks : [];
  return <section className="concept-node-page">
    <div className="node-header"><div className="node-header-left"><div className="node-large-icon">{isUnraid ? "▤" : "▣"}</div><div><div className="eyebrow">NODE / {node.machine_id}</div><h1>{node.display_name}</h1><div className="node-sub"><ConceptStatus node={{online:node.online,gaming_mode_until:activeGamingUntil(node)}}/><span>{operatingSystem}</span><span>Agent v{node.agent_version || "—"}</span><span>Kontakt {ago(node.last_seen_at)}</span></div></div></div><div className="node-actions">
      {!isUnraid && canDelete && <button type="button" className="outline-button" disabled={updatingGaming} onClick={() => void updateGamingMode(gamingActive ? 0 : 120)}><ConceptIcon name="bolt" size={16}/>{gamingActive ? "Gaming Mode beenden" : "Gaming Mode"}</button>}
      {canDelete && node.platform === "windows" && <button
        type="button"
        className="outline-button"
        disabled={updateCheckState !== "idle" || !node.online}
        title={node.online ? "Payload-Release und Installer-Update sofort prüfen statt bis zu 6 Stunden zu warten" : "Das Gerät ist offline"}
        onClick={() => void requestUpdateCheck()}
      >
        <RefreshCw size={16} className={updateCheckState === "sending" ? "spin" : ""} />
        {updateCheckState === "requested" ? "Update-Prüfung angefordert" : "Jetzt aktualisieren"}
      </button>}
      <button type="button" className="outline-button" onClick={() => setActionOpen((open) => !open)}>Aktionen ⌄</button>
      {actionOpen && <div className="action-menu"><button type="button" disabled={renaming} onClick={() => void rename()}>Gerät umbenennen</button>{canDelete && <button type="button" disabled={updatingRole} onClick={() => void toggleRole()}>{node.access_role === "beta_tester" ? "Zu Commander machen" : "Als Beta-Tester markieren"}</button>}{canDelete && !isUnraid && <><button type="button" disabled={updatingRelease} onClick={() => void changeUpdateChannel()}>Update-Kanal: {node.update_channel.toUpperCase()}</button><button type="button" disabled={updatingRelease} onClick={() => void assignRelease()}>{pendingRelease ? `Freigabe aufheben: ${pendingRelease.payload_version}` : "Update bewusst freigeben"}</button>{!pendingRelease && channelReleases.length > 1 && <select aria-label="Release auswählen" defaultValue="" onChange={(event) => { if(event.target.value) void setRelease(event.target.value); }}><option value="">Release auswählen …</option>{channelReleases.map((release) => <option key={release.release_id} value={release.release_id}>{release.payload_version}</option>)}</select>}</>}{canDelete && <button type="button" className="danger" disabled={forgetting} onClick={() => void forget()}>Gerät vergessen</button>}</div>}
    </div></div>
    <div className="node-meta"><span>Physisches Gerät <b>{node.physical_device_name || node.display_name}</b></span><span>Plattform <b>{node.platform}</b></span><span>Update <b>{pendingRelease?.payload_version || node.update_channel.toUpperCase()}</b></span><span>Datenfrische <b>{node.online ? "Live" : ago(node.last_seen_at)}</b></span></div>
    <NowPlayingCard node={node} token={token} canManage={canDelete}/>
    <div className="node-chart-card"><div className="card-head"><div><div className="eyebrow">Verlauf</div><h2>Ressourcen im Verlauf</h2></div><span className="muted-small">Letzte {points.length} Messpunkte</span></div><div className="chart-key"><span><i style={{background:"var(--accent)"}}/> CPU</span><span><i style={{background:"var(--purple)"}}/> GPU</span></div><div className="dual-chart"><ConceptSparkline values={cpuSeries} color="var(--accent)" height={190} fill/><ConceptSparkline values={gpuSeries} color="var(--purple)" height={190}/></div><div className="chart-axis"><span>Verlauf</span><span>Jetzt</span></div></div>
    <div className="metric-grid">
      <div className="metric-card"><div className="metric-title"><span>CPU</span><ConceptIcon name="activity" size={17}/></div><div className="metric-value">{num(cpu.percent).toFixed(1)}%</div><p>{cpuModel}</p><ConceptSparkline values={cpuSeries} height={48}/><div className="metric-items"><div><span>Temperatur</span><b>{typeof cpu.temperature_c === "number" ? `${num(cpu.temperature_c).toFixed(0)} °C` : "—"}</b></div><div><span>Takt</span><b>{typeof cpu.frequency_mhz === "number" ? `${num(cpu.frequency_mhz).toFixed(0)} MHz` : "—"}</b></div></div></div>
      <div className="metric-card"><div className="metric-title"><span>Arbeitsspeicher</span><ConceptIcon name="grid" size={17}/></div><div className="metric-value">{num(memory.used_gb).toFixed(1)} GB</div><p>von {num(memory.total_gb).toFixed(1)} GB belegt</p><div className="metric-meter"><ConceptMeter value={num(memory.percent)}/></div><div className="metric-items"><div><span>Auslastung</span><b>{num(memory.percent).toFixed(1)}%</b></div></div></div>
      {!isUnraid && <div className="metric-card"><div className="metric-title"><span>Grafikprozessor</span><ConceptIcon name="bolt" size={17}/></div><div className="metric-value">{m.gpus?.length ? `${num(gpu.percent).toFixed(1)}%` : "—"}</div><p>{gpuModel}</p><ConceptSparkline values={gpuSeries} color="var(--blue)" height={48}/><div className="metric-items"><div><span>Temperatur</span><b>{typeof (lhmGpu.temperature_c ?? gpu.temperature_c) === "number" ? `${num(lhmGpu.temperature_c ?? gpu.temperature_c).toFixed(0)} °C` : "—"}</b></div><div><span>Leistung</span><b>{typeof (lhmGpu.power_w ?? gpu.power_w) === "number" ? `${num(lhmGpu.power_w ?? gpu.power_w).toFixed(1)} W` : "—"}</b></div></div></div>}
      <div className="metric-card"><div className="metric-title"><span>Netzwerk</span><ConceptIcon name="chart" size={17}/></div><div className="metric-value">{num(network.download_mbps).toFixed(1)} Mb/s</div><p>↓ Download · {network.interface || "Automatisch"}</p><ConceptSparkline values={downSeries} height={48}/><div className="metric-items"><div><span>Upload</span><b>{num(network.upload_mbps).toFixed(1)} Mb/s</b></div><div><span>Monat ↓ / ↑</span><b>{monthlyNetwork?.available ? `${trafficBytes(monthlyNetwork.received_bytes)} / ${trafficBytes(monthlyNetwork.sent_bytes)}` : "—"}</b></div></div></div>
    </div>
    <div className="detail-bottom"><div className="detail-card"><ConceptSectionHead eyebrow="Speicher" title="Laufwerke"/>{storage.map((disk: Metrics, index: number) => <div className="disk-row" key={`${disk.mount || disk.name}-${index}`}><div><b>{disk.mount || disk.name || `Disk ${index + 1}`}</b><span>{num(disk.used_gb).toFixed(1)} / {num(disk.total_gb).toFixed(1)} GB</span></div><ConceptMeter value={num(disk.percent)}/><small>Lesen {num(disk.read_mbps).toFixed(1)} · Schreiben {num(disk.write_mbps).toFixed(1)} MiB/s</small></div>)}{!storage.length && <div className="empty">Keine Laufwerksdaten vorhanden.</div>}</div><HardwareSensorsCard metrics={m} isWindows={node.platform === "windows" && !isUnraid}/></div>
    {Array.isArray(cpu.per_core) && cpu.per_core.length > 0 && <div className="detail-card concept-core-load"><ConceptSectionHead eyebrow="CPU-Threads" title="Last pro Kern"/><div className="concept-core-bars">{cpu.per_core.map((value: unknown, index: number) => <div key={index} title={`Kern ${index + 1}: ${num(value).toFixed(1)}%`}><span>{index + 1}</span><ConceptMeter value={num(value)}/></div>)}</div></div>}
    {isUnraid && <div className="detail-bottom concept-unraid"><UnraidStorageCard metrics={m}/><div className="unraid-services-grid"><UnraidWorkloadCard title="Virtuelle Maschinen" icon={<MonitorCog size={16}/>} items={m.vms || []} kind="vm"/><UnraidWorkloadCard title="Docker-Container" icon={<Boxes size={16}/>} items={m.containers || []} kind="container"/></div></div>}
  </section>;
}

function StatisticsPage({
  nodes,
  summary,
  token,
  trafficResetRevision,
  canManage,
}: {
  nodes: Node[];
  summary: Summary | null;
  token: string;
  trafficResetRevision: number;
  canManage: boolean;
}) {
  const [view, setView] = useState<"fleet" | "playtime">(() => {
    try { return localStorage.getItem("ncc-statistics-view") === "playtime" ? "playtime" : "fleet"; } catch { return "fleet"; }
  });
  const chooseView = (value: "fleet" | "playtime") => {
    setView(value);
    try { localStorage.setItem("ncc-statistics-view", value); } catch { /* Only a convenience. */ }
  };
  const [traffic, setTraffic] = useState<Record<string, NetworkUsageSummary>>({});
  const [trafficHistory, setTrafficHistory] = useState<Record<string, NetworkHistorySample[]>>({});
  // The fleet itself is refreshed every five seconds.  Statistics requests may
  // take longer on a growing database, therefore use a stable node key and a
  // slower independent polling loop instead of cancelling every response.
  const trafficNodeKey = nodes.map((node) => node.node_id).sort().join("|");
  const trafficNodes = useMemo(
    () => [...nodes].sort((left, right) => left.node_id.localeCompare(right.node_id)),
    [trafficNodeKey],
  );
  useEffect(() => {
    let current = true;
    let monthlyBusy = false;
    let historyBusy = false;
    if (trafficResetRevision > 0) setTraffic({});
    const loadMonthly = async () => {
      if (monthlyBusy || document.visibilityState !== "visible") return;
      monthlyBusy = true;
      try {
        // A slow node must not hold back all traffic values. Bound concurrent
        // month scans so a growing database is not queried for every node at once.
        const pending = [...trafficNodes];
        const worker = async () => {
          while (current && document.visibilityState === "visible") {
            const node = pending.shift();
            if (!node) break;
            try {
              const value = await getJson<NetworkUsageSummary>(`/api/v1/fleet/nodes/${node.node_id}/network/month`, token, 90_000);
              if (current) setTraffic((previous) => ({ ...previous, [node.node_id]: value }));
            } catch { /* Retain the last successful value for this node. */ }
          }
        };
        await Promise.all(Array.from({ length: Math.min(2, pending.length) }, () => worker()));
      } finally { monthlyBusy = false; }
    };
    const loadHistory = async () => {
      if (historyBusy || document.visibilityState !== "visible") return;
      historyBusy = true;
      try {
        await Promise.all(trafficNodes.map(async (node) => {
          try {
            const value = await getJson<NetworkHistorySample[]>(`/api/v1/fleet/nodes/${node.node_id}/network/history?limit=48`, token);
            if (current) setTrafficHistory((previous) => ({ ...previous, [node.node_id]: value }));
          } catch { /* A failed history request must not hide monthly totals. */ }
        }));
      } finally { historyBusy = false; }
    };
    setTraffic((previous) => Object.fromEntries(Object.entries(previous).filter(([id]) => trafficNodes.some((node) => node.node_id === id))));
    void loadMonthly();
    void loadHistory();
    const monthlyRefresh = window.setInterval(() => void loadMonthly(), 300_000);
    const historyRefresh = window.setInterval(() => void loadHistory(), 30_000);
    const resume = () => { if (document.visibilityState === "visible") { void loadMonthly(); void loadHistory(); } };
    document.addEventListener("visibilitychange", resume);
    return () => { current = false; window.clearInterval(monthlyRefresh); window.clearInterval(historyRefresh); document.removeEventListener("visibilitychange", resume); };
  }, [trafficNodes, token, trafficResetRevision]);

  const measured = nodes.filter((node) => node.online && node.latest);
  const cpuThreads = (metrics: Metrics) => Math.max(1, num(metrics.cpu?.logical_cores || metrics.cpu?.threads));
  const totalThreads = measured.reduce((total, node) => total + cpuThreads(node.latest!.metrics), 0);
  const usedCpuThreads = measured.reduce(
    (total, node) => total + (num(node.latest!.metrics.cpu?.percent) / 100) * cpuThreads(node.latest!.metrics),
    0,
  );
  const fleetCpu = totalThreads ? (usedCpuThreads / totalThreads) * 100 : 0;
  const totalMemory = measured.reduce((total, node) => total + num(node.latest!.metrics.memory?.total_gb), 0);
  const usedMemory = measured.reduce((total, node) => total + num(node.latest!.metrics.memory?.used_gb), 0);
  const fleetMemory = totalMemory ? (usedMemory / totalMemory) * 100 : 0;
  const disks = measured.flatMap((node) => Array.isArray(node.latest!.metrics.disks) ? node.latest!.metrics.disks : []);
  const totalDisk = disks.reduce((total: number, disk: Metrics) => total + num(disk.total_gb), 0);
  const usedDisk = disks.reduce((total: number, disk: Metrics) => total + num(disk.used_gb), 0);
  const fleetDisk = totalDisk ? (usedDisk / totalDisk) * 100 : 0;
  const gpus: (Metrics & { nodeName: string })[] = measured.flatMap((node) =>
    Array.isArray(node.latest!.metrics.gpus)
      ? node.latest!.metrics.gpus.map((gpu: Metrics) => ({ ...gpu, nodeName: node.display_name }) as Metrics & { nodeName: string })
      : [],
  );
  const fleetGpu = gpus.length ? gpus.reduce((total, gpu) => total + num(gpu.percent), 0) / gpus.length : 0;
  const gpuScore = (gpu: Metrics) => {
    const declared = num(gpu.performance_score || gpu.tflops || gpu.vram_total_gb || gpu.memory_total_gb);
    if (declared) return declared * 10000;
    const modelNumber = Number(String(gpu.name || gpu.model || "").match(/\b(\d{3,4})\b/)?.[1] || 0);
    return modelNumber;
  };
  const strongestGpu = [...gpus].sort((left, right) => gpuScore(right) - gpuScore(left))[0];
  const totalReceived = Object.values(traffic).reduce((total, item) => total + item.received_bytes, 0);
  const totalSent = Object.values(traffic).reduce((total, item) => total + item.sent_bytes, 0);
  const trafficAvailable = Object.values(traffic).some((item) => item.available);
  const trafficDevices = Array.from(nodes.reduce((result, node) => {
    const key = node.physical_device_id || node.node_id;
    const current = result.get(key) || { key, name: node.physical_device_name || node.display_name, received: 0, sent: 0, available: false };
    const usage = traffic[node.node_id];
    if (usage?.available) {
      current.received += usage.received_bytes;
      current.sent += usage.sent_bytes;
      current.available = true;
    }
    result.set(key, current);
    return result;
  }, new Map<string, { key: string; name: string; received: number; sent: number; available: boolean }>()).values());
  const evaluatedDevices = trafficDevices.filter((device) => device.available).length;
  const percentOnline = summary?.total_nodes
    ? Math.round((summary.online_nodes / summary.total_nodes) * 100)
    : 0;
  const availability = [...nodes]
    .map((node) => ({ node, value: num(node.availability_percent) }))
    .sort((left, right) => right.value - left.value || right.node.uptime_record_seconds - left.node.uptime_record_seconds || left.node.display_name.localeCompare(right.node.display_name, "de"));
  const rankedLoad = [...measured]
    .map((node) => {
      const metrics = node.latest!.metrics;
      const gpuLoads = Array.isArray(metrics.gpus) ? metrics.gpus : [];
      const gpu = gpuLoads.length ? gpuLoads.reduce((total: number, item: Metrics) => total + num(item.percent), 0) / gpuLoads.length : 0;
      const values = [num(metrics.cpu?.percent), num(metrics.memory?.percent)];
      if (gpuLoads.length) values.push(gpu);
      return { node, value: values.reduce((total, item) => total + item, 0) / values.length };
    })
    .sort((left, right) => right.value - left.value)
    .slice(0, 5);
  const rankedTraffic = [...nodes]
    .sort((left, right) => {
      const rightTotal = (traffic[right.node_id]?.received_bytes || 0) + (traffic[right.node_id]?.sent_bytes || 0);
      const leftTotal = (traffic[left.node_id]?.received_bytes || 0) + (traffic[left.node_id]?.sent_bytes || 0);
      return rightTotal - leftTotal;
    })
    .slice(0, 5);
  const liveTraffic = useMemo(() => {
    const onlineIds = new Set(nodes.filter((node) => node.online).map((node) => node.node_id));
    const recent = Object.entries(trafficHistory)
      .filter(([nodeId]) => onlineIds.has(nodeId))
      .map(([, history]) => history.filter((point) => point.network).map((point) => ({ at: new Date(point.recorded_at).getTime(), network: point.network })));
    // Agents sample at different times. Align by time rather than array index,
    // otherwise a delayed node's old sample appears as current fleet traffic.
    const lastSlot = Math.floor(Date.now() / 10_000) * 10_000;
    return Array.from({ length: 30 }, (_, index) => {
      const slotEnd = lastSlot - (29 - index) * 10_000 + 10_000;
      return recent.reduce((total, history) => {
        const point = [...history].reverse().find((sample) => sample.at <= slotEnd && sample.at > slotEnd - 25_000);
        return {
          download: total.download + num(point?.network?.download_mbps),
          upload: total.upload + num(point?.network?.upload_mbps),
        };
      }, { download: 0, upload: 0 });
    });
  }, [trafficHistory, nodes]);

  const [selectedTrafficDirection, setSelectedTrafficDirection] = useState<"download" | "upload">("download");
  const selectedTotal = selectedTrafficDirection === "download" ? totalReceived : totalSent;
  const trafficSeries = liveTraffic.map((sample) => selectedTrafficDirection === "download" ? sample.download : sample.upload);
  const trafficRanking = [...trafficDevices].sort((left, right) =>
    (selectedTrafficDirection === "download" ? right.received - left.received : right.sent - left.sent),
  ).slice(0, 5);
  const averageAvailability = availability.length
    ? availability.reduce((total, entry) => total + entry.value, 0) / availability.length
    : 0;
  return <>
    <div className="page-intro"><div><div className="eyebrow">INSIGHTS / FLEET</div><h1>Muster erkennen.</h1><p>{view === "playtime" ? "Welche Spiele wann und wie lange laufen, mit den Hardware-Werten dazu." : "Verfügbarkeit, Rekorde und Traffic über die gesamte Fleet."}</p></div>
      <div className="segmented stats-view-switch"><button type="button" className={view === "fleet" ? "selected" : ""} onClick={() => chooseView("fleet")}>Fleet</button><button type="button" className={view === "playtime" ? "selected" : ""} onClick={() => chooseView("playtime")}>Spielzeit</button></div>
    </div>
    {view === "playtime" ? <PlaytimeStatistics nodes={nodes} token={token} canManage={canManage}/> : <>
    <div className="stats-summary">
      <div><small>Verfügbarkeit seit Aufnahme</small><strong>{averageAvailability.toFixed(2)}<span>%</span></strong><p>Durchschnitt aller OS-Profile</p></div>
      <div><small>Download in diesem Monat</small><strong>{trafficAvailable ? trafficBytes(totalReceived) : "…"}</strong><p>{trafficAvailable ? `${evaluatedDevices}/${trafficDevices.length} Geräte ausgewertet` : "Monatswerte werden berechnet"}</p></div>
      <div><small>Upload in diesem Monat</small><strong>{trafficAvailable ? trafficBytes(totalSent) : "…"}</strong><p>{trafficAvailable ? `${evaluatedDevices}/${trafficDevices.length} Geräte ausgewertet` : "Monatswerte werden berechnet"}</p></div>
    </div>
    <div className="stats-layout">
      <div className="detail-card">
        <ConceptSectionHead eyebrow="Bestenliste" title="Verfügbarkeits-Rangliste" aside={<span className="muted-small">Seit Aufnahme des Geräts</span>}/>
        <div className="ranking">{availability.map(({node, value}, index) => <div className="ranking-entry" key={node.node_id}>
          <span className="rank-number">{String(index + 1).padStart(2, "0")}</span><span className="rank-name"><b>{node.display_name}</b><small>{node.platform}</small></span>
          <span className="rank-bar"><ConceptMeter value={value}/></span><span className="rank-percent">{value.toFixed(2)}%</span><span className="rank-record">Rekord {duration(node.uptime_record_seconds)}</span>
        </div>)}</div>
      </div>
      <div className="detail-card">
        <ConceptSectionHead eyebrow="Traffic-Vergleich" title="Netzwerk nach Gerät"/>
        <div className="segmented stats-tabs"><button type="button" className={selectedTrafficDirection === "download" ? "selected" : ""} onClick={() => setSelectedTrafficDirection("download")}>Download</button><button type="button" className={selectedTrafficDirection === "upload" ? "selected" : ""} onClick={() => setSelectedTrafficDirection("upload")}>Upload</button></div>
        <ConceptSparkline values={trafficSeries} color="var(--mint)" height={172} fill/>
        <div className="chart-axis"><span>Verlauf der letzten Messpunkte</span><span>Jetzt</span></div>
        <div className="traffic-breakdown">{trafficRanking.map((device) => {
          const value = selectedTrafficDirection === "download" ? device.received : device.sent;
          return <div key={device.key}><span>{device.name}</span><ConceptMeter value={selectedTotal ? value / selectedTotal * 100 : 0}/><b>{device.available ? trafficBytes(value) : "—"}</b></div>;
        })}</div>
      </div>
    </div>
    </>}
  </>;

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
          <span className="eyebrow">Live-Telemetrie</span>
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
              <span>CPU-Last</span>
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
              <span>RAM-Auslastung</span>
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
          <header><div className="chart-icon blue"><Network size={17} /></div><div><span>Netzwerk-Download</span><strong>{num(network.download_mbps).toFixed(1)} Mbps</strong></div></header>
          <Sparkline points={points} metric={(m) => num(m.network?.download_mbps)} maxValue={Math.max(10, ...points.map((point) => num(point.metrics.network?.download_mbps)))} color="var(--blue)" />
        </article>
        <article className="surface chart-card">
          <header><div className="chart-icon purple"><Network size={17} /></div><div><span>Netzwerk-Upload</span><strong>{num(network.upload_mbps).toFixed(1)} Mbps</strong></div></header>
          <Sparkline points={points} metric={(m) => num(m.network?.upload_mbps)} maxValue={Math.max(10, ...points.map((point) => num(point.metrics.network?.upload_mbps)))} color="var(--purple)" />
        </article>
        <article className="surface chart-card">
          <header><div className="chart-icon blue"><HardDrive size={17} /></div><div><span>Höchste Laufwerksbelegung</span><strong>{diskUse.toFixed(1)}%</strong></div></header>
          <Sparkline points={points} metric={(m) => Math.max(0, ...(m.disks || []).map((disk: Metrics) => num(disk.percent)))} color="var(--blue)" />
        </article>
        {typeof cpu.temperature_c === "number" && <article className="surface chart-card">
          <header><div className="chart-icon red"><Cpu size={17} /></div><div><span>CPU-Temperatur</span><strong>{num(cpu.temperature_c).toFixed(0)} °C</strong></div></header>
          <Sparkline points={points} metric={(m) => num(m.cpu?.temperature_c)} color="var(--amber)" />
        </article>}
        <article className="surface chart-card">
          <header>
            <div className="chart-icon purple">
              <MonitorCog size={17} />
            </div>
            <div>
              <span>GPU-Last</span>
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
            <span className="eyebrow">Geräteinformationen</span>
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

function ChatAttachmentView({ attachment, token, onOpen }: { attachment: ChatAttachment; token: string; onOpen: (attachment: ChatAttachment, url: string, kind: "image" | "video" | "audio" | "pdf") => void }) {
  const [url, setUrl] = useState("");
  const [previewRequested, setPreviewRequested] = useState(false);
  const [previewError, setPreviewError] = useState(false);
  const [openPdfWhenReady, setOpenPdfWhenReady] = useState(false);
  const imageRef = useRef<HTMLButtonElement>(null);
  const kind = attachment.content_type.startsWith("image/") ? "image" : attachment.content_type.startsWith("video/") ? "video" : attachment.content_type.startsWith("audio/") ? "audio" : attachment.content_type === "application/pdf" ? "pdf" : "file";
  useEffect(() => {
    if (kind !== "image" || previewRequested || previewError) return;
    const element = imageRef.current;
    if (!element) return;
    if (typeof IntersectionObserver === "undefined") {
      setPreviewRequested(true);
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        setPreviewRequested(true);
        observer.disconnect();
      }
    }, { rootMargin: "160px" });
    observer.observe(element);
    return () => observer.disconnect();
  }, [kind, previewError, previewRequested]);
  useEffect(() => {
    // The chat history must not download attachments outside the viewport or
    // large media that nobody has asked to preview.
    if (kind === "file" || !previewRequested) return;
    let active = true;
    let objectUrl = "";
    setUrl("");
    fetch(attachment.url, { headers: headers(token) }).then(async (response) => {
      if (!response.ok) throw new Error("MEDIA_REQUEST");
      const blob = await response.blob();
      if (!active) return;
      objectUrl = URL.createObjectURL(blob);
      setUrl(objectUrl);
    }).catch(() => {
      if (active) {
        setPreviewError(true);
        setPreviewRequested(false);
        setOpenPdfWhenReady(false);
      }
    });
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [attachment.url, kind, token, previewRequested]);
  useEffect(() => {
    if (kind === "pdf" && url && openPdfWhenReady) {
      setOpenPdfWhenReady(false);
      onOpen(attachment, url, "pdf");
    }
  }, [attachment, kind, onOpen, openPdfWhenReady, url]);
  const download = async () => {
    const response = await fetch(attachment.url, { headers: headers(token) });
    if (!response.ok) return;
    const temporary = URL.createObjectURL(await response.blob());
    const link = document.createElement("a"); link.href = temporary; link.download = attachment.name; link.click();
    // Keep the blob alive until the browser has started saving the download.
    window.setTimeout(() => URL.revokeObjectURL(temporary), 60_000);
  };
  if (kind === "image") return <button ref={imageRef} type="button" className="chat-media image" onClick={() => { if (url) onOpen(attachment, url, "image"); else { setPreviewError(false); setPreviewRequested(true); } }}>{url ? <img src={url} alt={attachment.name} /> : <div className="chat-image-placeholder"><ImageIcon size={22} /><small>{previewRequested ? "Bild wird geladen …" : previewError ? "Bild erneut laden" : "Bildvorschau laden"}</small></div>}<span><ImageIcon size={14} />{attachment.name}<Maximize2 size={13} /></span></button>;
  if (kind === "video") return <div className="chat-media video"><header><Film size={14} />{attachment.name}</header>{url ? <video src={url} controls preload="metadata" /> : <button type="button" onClick={() => { setPreviewError(false); setPreviewRequested(true); }} disabled={previewRequested}>{previewRequested ? "Vorschau wird geladen …" : previewError ? "Video-Vorschau erneut laden" : "Video-Vorschau laden"}</button>}</div>;
  if (kind === "audio") return <div className="chat-media audio"><header><Music2 size={14} />{attachment.name}</header>{url ? <audio src={url} controls /> : <button type="button" onClick={() => { setPreviewError(false); setPreviewRequested(true); }} disabled={previewRequested}>{previewRequested ? "Vorschau wird geladen …" : previewError ? "Audio-Vorschau erneut laden" : "Audio-Vorschau laden"}</button>}</div>;
  if (kind === "pdf") return <button type="button" className="chat-media document" onClick={() => { if (url) onOpen(attachment, url, "pdf"); else { setPreviewError(false); setOpenPdfWhenReady(true); setPreviewRequested(true); } }}><FileText size={21} /><span><b>{attachment.name}</b><small>{previewRequested && !url ? "PDF wird geladen …" : previewError ? "PDF-Vorschau erneut öffnen" : "PDF-Vorschau öffnen"}</small></span><Maximize2 size={14} /></button>;
  return <button type="button" className="chat-attachment" onClick={() => void download()}><Paperclip size={14} /><span>{attachment.name}</span><small>{trafficBytes(attachment.size)}</small><Download size={13} /></button>;
}

function FleetChat({ token, identity }: { token: string; identity: DashboardUser | null }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [participants, setParticipants] = useState<ChatParticipant[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [participantsLoading, setParticipantsLoading] = useState(true);
  const [body, setBody] = useState("");
  const [format, setFormat] = useState<"plain" | "markdown">("plain");
  const [attachment, setAttachment] = useState<File | null>(null);
  const [sending, setSending] = useState(false);
  const [olderLoading, setOlderLoading] = useState(false);
  const [hasOlder, setHasOlder] = useState(false);
  const [unread, setUnread] = useState(0);
  const [chatError, setChatError] = useState("");
  const [preview, setPreview] = useState<{ attachment: ChatAttachment; url: string; kind: "image" | "video" | "audio" | "pdf" } | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const newestIdRef = useRef("");
  const oldestIdRef = useRef("");
  const knownMessageIdsRef = useRef<Set<string>>(new Set());
  const loadedRef = useRef(false);
  const activeTokenRef = useRef(token);
  activeTokenRef.current = token;
  const pollingTokenRef = useRef<string | null>(null);
  const atBottomRef = useRef(true);
  const scrollRef = useRef<"bottom" | { top: number; height: number } | null>(null);
  const loadLatest = useCallback(async () => {
    if (pollingTokenRef.current === token) return;
    pollingTokenRef.current = token;
    try {
      const initial = !loadedRef.current || !newestIdRef.current;
      const cursor = newestIdRef.current;
      const url = initial ? "/api/v1/fleet/chat/messages?limit=50" : `/api/v1/fleet/chat/messages?limit=100&after=${encodeURIComponent(cursor)}`;
      const incoming = await getJson<ChatMessage[]>(url, token);
      if (activeTokenRef.current !== token) return;
      if (initial) {
        incoming.forEach((message) => knownMessageIdsRef.current.add(message.message_id));
        loadedRef.current = true;
        setHistoryLoading(false);
        setHasOlder(incoming.length === 50);
        oldestIdRef.current = incoming[0]?.message_id || "";
        scrollRef.current = "bottom";
        // A send can finish while the initial history request is in flight.
        // Keep that acknowledged message until the next cursor poll sees it.
        setMessages((previous) => {
          const seen = new Set(incoming.map((message) => message.message_id));
          return [...incoming, ...previous.filter((message) => !seen.has(message.message_id))];
        });
      } else if (incoming.length) {
        const novel = incoming.filter((message) => !knownMessageIdsRef.current.has(message.message_id));
        incoming.forEach((message) => knownMessageIdsRef.current.add(message.message_id));
        if (novel.length && atBottomRef.current) scrollRef.current = "bottom";
        else if (novel.length) setUnread((count) => count + novel.length);
        if (novel.length) setMessages((previous) => {
          const seen = new Set(previous.map((message) => message.message_id));
          return [...previous, ...novel.filter((message) => !seen.has(message.message_id))];
        });
      }
      if (incoming.length) newestIdRef.current = incoming[incoming.length - 1].message_id;
      setChatError("");
    } finally {
      if (pollingTokenRef.current === token) pollingTokenRef.current = null;
    }
  }, [token]);
  const loadParticipants = useCallback(async () => {
    const incoming = await getJson<ChatParticipant[]>("/api/v1/fleet/chat/participants", token);
    if (activeTokenRef.current !== token) return;
    setParticipants(incoming);
    setParticipantsLoading(false);
  }, [token]);
  useEffect(() => {
    loadedRef.current = false;
    newestIdRef.current = "";
    oldestIdRef.current = "";
    knownMessageIdsRef.current.clear();
    setMessages([]);
    setParticipants([]);
    setHistoryLoading(true);
    setParticipantsLoading(true);
    setUnread(0);
  }, [token]);
  useEffect(() => {
    let current = true;
    const refresh = () => {
      if (document.visibilityState === "visible") void loadLatest().catch(() => {
        if (!current) return;
        setHistoryLoading(false);
        setChatError("Fleet Chat ist gerade nicht erreichbar.");
      });
    };
    refresh();
    void loadParticipants().catch(() => { if (current) setParticipantsLoading(false); });
    const messagesTimer = window.setInterval(refresh, 5000);
    const participantsTimer = window.setInterval(() => {
      if (document.visibilityState === "visible") void loadParticipants().catch(() => { if (current) setParticipantsLoading(false); });
    }, 60000);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      current = false;
      clearInterval(messagesTimer);
      clearInterval(participantsTimer);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [loadLatest, loadParticipants]);
  useLayoutEffect(() => {
    const list = listRef.current;
    if (!list || !scrollRef.current) return;
    if (scrollRef.current === "bottom") list.scrollTop = list.scrollHeight;
    else list.scrollTop = scrollRef.current.top + list.scrollHeight - scrollRef.current.height;
    scrollRef.current = null;
  }, [messages]);
  const loadOlder = async () => {
    if (!oldestIdRef.current || olderLoading) return;
    setOlderLoading(true);
    try {
      const list = listRef.current;
      const older = await getJson<ChatMessage[]>(`/api/v1/fleet/chat/messages?limit=50&before=${encodeURIComponent(oldestIdRef.current)}`, token);
      if (activeTokenRef.current !== token) return;
      setHasOlder(older.length === 50);
      if (older.length) {
        older.forEach((message) => knownMessageIdsRef.current.add(message.message_id));
        oldestIdRef.current = older[0].message_id;
        if (list) scrollRef.current = { top: list.scrollTop, height: list.scrollHeight };
        setMessages((previous) => {
          const seen = new Set(previous.map((message) => message.message_id));
          return [...older.filter((message) => !seen.has(message.message_id)), ...previous];
        });
      }
    } catch { if (activeTokenRef.current === token) setChatError("Ältere Nachrichten konnten nicht geladen werden."); }
    finally { setOlderLoading(false); }
  };
  const send = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!body.trim() && !attachment) return;
    if (attachment && attachment.size > 100 * 1024 * 1024) {
      setChatError("Der Anhang darf höchstens 100 MB groß sein.");
      return;
    }
    setSending(true);
    setChatError("");
    try {
      let sent: ChatMessage;
      if (attachment) {
        const data = new FormData();
        data.set("file", attachment);
        data.set("body", body);
        data.set("body_format", format);
        const response = await fetch("/api/v1/fleet/chat/uploads", { method: "POST", headers: headers(token), body: data });
        if (!response.ok) throw new Error("REQUEST");
        sent = await response.json() as ChatMessage;
      } else {
        sent = await postJson<ChatMessage>("/api/v1/fleet/chat/messages", token, { body, body_format: format });
      }
      if (activeTokenRef.current !== token) return;
      knownMessageIdsRef.current.add(sent.message_id);
      if (!oldestIdRef.current) oldestIdRef.current = sent.message_id;
      setBody("");
      setAttachment(null);
      const input = document.getElementById("fleet-chat-file") as HTMLInputElement | null;
      if (input) input.value = "";
      atBottomRef.current = true;
      scrollRef.current = "bottom";
      setUnread(0);
      setMessages((previous) => previous.some((item) => item.message_id === sent.message_id) ? previous : [...previous, sent]);
      void loadLatest().catch(() => setChatError("Nachricht gesendet; der neueste Verlauf konnte nicht geladen werden."));
    } catch {
      if (activeTokenRef.current === token) setChatError("Nachricht konnte nicht gesendet werden. Bitte erneut versuchen.");
    } finally { setSending(false); }
  };
  return <section className="concept-chat-page">
    <div className="page-intro"><div><div className="eyebrow">COLLABORATION / FLEET</div><h1>Fleet Chat.</h1><p>Absprachen und Medien an einem eigenen Ort, getrennt von Telemetrie und Warnungen.</p></div></div>
    <div className="chat-shell">
      <div className="chat-heading"><div className="chat-channel-icon">#</div><div><b>fleet-operations</b><small>Private Fleet · Nachrichten bleiben auf dem NCC-Server</small></div><span className="chat-members">● {participantsLoading ? "Mitglieder werden geladen" : `${participants.length} Mitglieder`}</span></div>
      <div className="chat-messages" ref={listRef} onScroll={(event) => {
        const list = event.currentTarget;
        atBottomRef.current = list.scrollHeight - list.scrollTop - list.clientHeight < 90;
        if (atBottomRef.current) setUnread(0);
      }}>
        {hasOlder && <button type="button" className="chat-load-older" disabled={olderLoading} onClick={() => void loadOlder()}>{olderLoading ? "Lade Verlauf …" : "Ältere Nachrichten laden"}</button>}
        {messages.map((message, index) => {
          const date = new Date(message.created_at);
          const day = date.toLocaleDateString("de-DE", { day: "numeric", month: "long", year: "numeric" });
          const previousDay = index ? new Date(messages[index - 1].created_at).toDateString() : "";
          const mine = identity?.user_id ? message.sender_user_id === identity.user_id : message.sender_name === identity?.username;
          return <React.Fragment key={message.message_id}>
            {date.toDateString() !== previousDay && <div className="chat-day">{day.toUpperCase()}</div>}
            <div className={`chat-message${mine ? " mine" : ""}`}>
              <div className="chat-avatar">{message.sender_name.slice(0, 1).toUpperCase()}</div>
              <div className="chat-message-content"><div className="message-meta"><b>{message.sender_name}</b><span>{date.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}</span>{message.body_format === "markdown" && <span>MARKDOWN</span>}</div>{message.body && (message.body_format === "markdown" ? <div className="message-body markdown"><React.Suspense fallback={<p>{message.body}</p>}><Markdown skipHtml disallowedElements={["img"]} components={{ a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" /> }}>{message.body}</Markdown></React.Suspense></div> : <p className="message-body">{message.body}</p>)}{message.attachment && <ChatAttachmentView attachment={message.attachment} token={token} onOpen={(nextAttachment, url, kind) => setPreview({ attachment: nextAttachment, url, kind })} />}</div>
            </div>
          </React.Fragment>;
        })}
        {!messages.length && <div className="chat-empty"><MessageSquare size={34} /><strong>{historyLoading ? "Chat-Verlauf wird geladen." : chatError ? "Chat-Verlauf nicht erreichbar." : "Der Fleet Chat ist bereit."}</strong><span>{historyLoading ? "Nachrichten werden vom NCC-Server abgerufen." : chatError ? "Die Verbindung wird automatisch erneut geprüft." : "Schreib die erste Nachricht an dein Team."}</span></div>}
      </div>
      {unread > 0 && <button type="button" className="chat-new-messages" onClick={() => { if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight; setUnread(0); }}>{unread} neue {unread === 1 ? "Nachricht" : "Nachrichten"} ↓</button>}
      <form className="chat-compose" ref={formRef} onSubmit={(event) => void send(event)}>
        <div className="chat-controls"><label>Format<select value={format} onChange={(event) => setFormat(event.target.value as "plain" | "markdown")}><option value="plain">Text</option><option value="markdown">Markdown</option></select></label></div>
        {attachment && <div className="attached">▧ {attachment.name} <button type="button" onClick={() => setAttachment(null)} aria-label="Anhang entfernen">×</button></div>}
        <div className="compose-row"><label className="attach-button" title="Datei anhängen" aria-label="Datei anhängen">＋<input id="fleet-chat-file" type="file" onChange={(event) => setAttachment(event.target.files?.[0] || null)} hidden /></label><textarea value={body} onChange={(event) => setBody(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); formRef.current?.requestSubmit(); } }} placeholder="Nachricht an #fleet-operations…" maxLength={20000} rows={2} disabled={sending} aria-label="Nachricht" /><button className="primary-button" disabled={sending || (!body.trim() && !attachment)} type="submit">{sending ? "Sende …" : "Senden"} <ConceptIcon name="arrow" size={16}/></button></div>
        {chatError && <small className="form-error" role="alert">{chatError}</small>}
        <small>Enter senden · Umschalt+Enter neue Zeile · Anhänge bis 100 MB</small>
      </form>
    </div>
    {preview && <div className="chat-preview-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setPreview(null)}><section className="chat-preview"><header><div><span className="eyebrow">Dateivorschau</span><h2>{preview.attachment.name}</h2></div><button onClick={() => setPreview(null)} aria-label="Vorschau schließen"><X size={18} /></button></header><div className="chat-preview-content">{preview.kind === "image" ? <img src={preview.url} alt={preview.attachment.name} /> : <iframe src={preview.url} title={preview.attachment.name} />}</div><footer><span>{(preview.attachment.size / 1024 / 1024).toFixed(1)} MB</span><a href={preview.url} download={preview.attachment.name}><Download size={15} />Download</a></footer></section></div>}
  </section>;
}

function AlertsPage({ alerts, canClear, onClear }: { alerts: AlertRecord[]; canClear: boolean; onClear: () => Promise<void> }) {
  const active = alerts.filter((alert) => alert.active);
  const [clearing, setClearing] = useState(false);
  const [filter, setFilter] = useState("Alle");
  const [severity, setSeverity] = useState("Alle Schweregrade");
  const [expanded, setExpanded] = useState<string | null>(null);
  const shown = alerts.filter((alert) => (filter === "Alle" || (filter === "Aktiv" ? alert.active : !alert.active)) && (severity === "Alle Schweregrade" || alert.severity === severity));
  return <>
    <div className="page-intro"><div><div className="eyebrow">INCIDENT / CENTER</div><h1>Warnungszentrale.</h1><p>Vorfälle mit Kontext, Verlauf und klaren nächsten Schritten.</p></div>{canClear && active.length > 0 && <button type="button" className="outline-button" disabled={clearing} onClick={() => { if (window.confirm("Alle aktiven Warnungen als erledigt markieren?")) { setClearing(true); void onClear().finally(() => setClearing(false)); } }}>{clearing ? "Wird erledigt …" : "Alle erledigt"}</button>}</div>
    <div className="alert-summary"><div><strong>{active.length}</strong><span>Aktiv</span></div><div><strong>{active.filter((alert) => alert.severity === "critical").length}</strong><span>Kritisch</span></div><div><strong>{alerts.length - active.length}</strong><span>Gelöst</span></div></div>
    <div className="filter-bar alert-filters"><div className="segmented">{["Alle", "Aktiv", "Gelöst"].map((value) => <button type="button" key={value} className={filter === value ? "selected" : ""} onClick={() => setFilter(value)}>{value}</button>)}</div><select value={severity} onChange={(event) => setSeverity(event.target.value)}><option>Alle Schweregrade</option><option value="critical">Kritisch</option><option value="warning">Warnung</option></select></div>
    <div className="alert-list">{shown.length ? shown.map((alert) => <div className={`alert-item ${alert.active ? alert.severity : "resolved"}`} key={alert.alert_id}><div className="alert-item-main" role="button" tabIndex={0} onClick={() => setExpanded(expanded === alert.alert_id ? null : alert.alert_id)} onKeyDown={(event) => { if (event.key === "Enter") setExpanded(expanded === alert.alert_id ? null : alert.alert_id); }}><div className={`alert-indicator ${alert.active ? alert.severity : "info"}`}><ConceptIcon name="alert" size={19}/></div><div className="alert-copy"><div className="alert-title-line"><span className={`severity ${alert.severity}`}>{alert.severity.toUpperCase()}</span><span className="alert-state">{alert.active ? "Aktiv" : "Gelöst"}</span><span>{new Date(alert.opened_at).toLocaleString("de-DE")}</span></div><h3>{alert.message}</h3><p>{alert.display_name} · {alert.kind.toUpperCase()}</p></div><span className="expand-caret">{expanded === alert.alert_id ? "⌃" : "⌄"}</span></div>{expanded === alert.alert_id && <div className="alert-expanded"><div className="eyebrow">Ereignisverlauf</div><div className="history-line"><span/>Erkannt {new Date(alert.opened_at).toLocaleString("de-DE")}</div>{!alert.active && <div className="history-line"><span/>Behoben {new Date(alert.resolved_at || alert.updated_at).toLocaleString("de-DE")}</div>}</div>}</div>) : <div className="empty">Keine Vorfälle in dieser Auswahl.</div>}</div>
  </>;
}

function DashboardUsers({ token, identity, canManage }: { token: string; identity: DashboardUser | null; canManage: boolean }) {
  const [users, setUsers] = useState<DashboardUser[]>([]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<AccessRole>("beta_tester");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const refresh = useCallback(async () => {
    if (canManage) setUsers(await getJson<DashboardUser[]>("/api/v1/users", token));
  }, [canManage, token]);
  useEffect(() => { void refresh().catch(() => setMessage("Benutzer konnten nicht geladen werden.")); }, [refresh]);
  const create = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setMessage("");
    try {
      await postJson<DashboardUser>("/api/v1/users", token, { username: username.trim().toLowerCase(), password, role });
      setUsername(""); setPassword(""); await refresh(); setMessage("Benutzerkonto erstellt.");
    } catch { setMessage("Benutzerkonto konnte nicht erstellt werden. Name prüfen oder anderen Namen wählen."); }
    finally { setBusy(false); }
  };
  const change = async (user: DashboardUser, patch: { role?: AccessRole; active?: boolean }) => {
    setBusy(true); setMessage("");
    try {
      const response = await fetch(`/api/v1/users/${user.user_id}`, { method: "PATCH", headers: { ...headers(token), "Content-Type": "application/json" }, body: JSON.stringify(patch) });
      if (!response.ok) throw new Error("REQUEST");
      await refresh(); setMessage("Benutzerkonto aktualisiert.");
    } catch { setMessage("Änderung fehlgeschlagen. Der letzte Commander muss aktiv bleiben."); }
    finally { setBusy(false); }
  };
  const changePassword = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setMessage("");
    try {
      const response = await fetch("/api/v1/users/password", { method: "POST", headers: { ...headers(token), "Content-Type": "application/json" }, body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }) });
      if (!response.ok) throw new Error("REQUEST");
      setCurrentPassword(""); setNewPassword(""); setMessage("Passwort geändert; andere Sitzungen wurden abgemeldet.");
    } catch { setMessage("Passwort konnte nicht geändert werden."); }
    finally { setBusy(false); }
  };
  return <section className="surface settings-card dashboard-users-card">
    <header className="section-head"><div><span className="eyebrow">ZUGANG / FLEET CHAT</span><h2>Benutzerkonten</h2></div><UserPlus size={19} /></header>
    <p>Du bist als <b>{identity?.username || "Commander"}</b> angemeldet. Fleet Chat zeigt diesen Namen als Absender.</p>
    {identity?.managed && <form className="dashboard-user-form" onSubmit={(event) => void changePassword(event)}>
      <h3>Eigenes Passwort ändern</h3>
      <input type="password" autoComplete="current-password" placeholder="Aktuelles Passwort" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required />
      <input type="password" autoComplete="new-password" placeholder="Neues Passwort (mindestens 12 Zeichen)" minLength={12} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required />
      <button className="outline-button" type="submit" disabled={busy}>Passwort ändern</button>
    </form>}
    {canManage && <>
      <div className="dashboard-user-list">{users.map((user) => <div key={user.user_id} className="dashboard-user-row">
        <span><b>{user.username}</b><small>{user.active ? "Aktiv" : "Deaktiviert"}</small></span>
        <select aria-label={`Rolle von ${user.username}`} value={user.role} disabled={busy} onChange={(event) => void change(user, { role: event.target.value as AccessRole })}><option value="commander">Commander</option><option value="beta_tester">Beta-Tester</option></select>
        <button type="button" className="outline-button" disabled={busy || user.user_id === identity?.user_id} onClick={() => void change(user, { active: !user.active })}>{user.active ? "Deaktivieren" : "Aktivieren"}</button>
      </div>)}</div>
      <form className="dashboard-user-form" onSubmit={(event) => void create(event)}>
        <h3>Benutzer hinzufügen</h3>
        <input aria-label="Benutzername" placeholder="Benutzername" autoComplete="off" value={username} onChange={(event) => setUsername(event.target.value)} required />
        <input aria-label="Initiales Passwort" type="password" autoComplete="new-password" placeholder="Passwort (mindestens 12 Zeichen)" minLength={12} value={password} onChange={(event) => setPassword(event.target.value)} required />
        <select aria-label="Neue Benutzerrolle" value={role} onChange={(event) => setRole(event.target.value as AccessRole)}><option value="beta_tester">Beta-Tester</option><option value="commander">Commander</option></select>
        <button className="primary" type="submit" disabled={busy}>Benutzer erstellen</button>
      </form>
    </>}
    {message && <small className="traffic-reset-message" role="status">{message}</small>}
  </section>;
}

function SettingsPage({
  theme,
  serverVersion,
  nodes,
  onTheme,
  onSwitchAccess,
  policy,
  onPolicy,
  telegram,
  onTelegram,
  onTelegramTest,
  canManageTelegram,
  canResetTraffic,
  onResetTraffic,
  releases,
  onRegisterRelease,
  canManageReleases,
  token,
  identity,
}: {
  theme: Theme;
  serverVersion: string | null;
  nodes: Node[];
  onTheme: (v: Theme) => void;
  onSwitchAccess: () => void;
  policy: AlertPolicy | null;
  onPolicy: (policy: AlertPolicy) => Promise<void>;
  telegram: TelegramSettings | null;
  onTelegram: (settings: TelegramSettings) => Promise<void>;
  onTelegramTest: () => Promise<void>;
  canManageTelegram: boolean;
  canResetTraffic: boolean;
  onResetTraffic: () => Promise<void>;
  releases: AgentRelease[];
  onRegisterRelease: (manifest: Record<string, unknown>) => Promise<void>;
  canManageReleases: boolean;
  token: string;
  identity: DashboardUser | null;
}) {
  const [draft, setDraft] = useState<AlertPolicy | null>(policy);
  const [telegramDraft, setTelegramDraft] = useState<TelegramSettings | null>(telegram);
  const [telegramMessage, setTelegramMessage] = useState("");
  const [testingTelegram, setTestingTelegram] = useState(false);
  const [resettingTraffic, setResettingTraffic] = useState(false);
  const [trafficResetMessage, setTrafficResetMessage] = useState("");
  const [releaseManifest, setReleaseManifest] = useState("");
  const [releaseMessage, setReleaseMessage] = useState("");
  useEffect(() => setDraft(policy), [policy]);
  useEffect(() => setTelegramDraft(telegram), [telegram]);
  const agentVersions = Array.from(nodes.reduce((counts, node) => {
    const version = node.agent_version || "Unbekannt";
    counts.set(version, (counts.get(version) || 0) + 1);
    return counts;
  }, new Map<string, number>()).entries()).sort(([left], [right]) => left.localeCompare(right));
  return (
    <><div className="page-intro"><div><div className="eyebrow">PREFERENCES / CONTROL</div><h1>Einstellungen.</h1><p>Schwellenwerte, Benachrichtigungen und Zugänge für deine Fleet.</p></div></div><div className="settings-grid concept-settings-grid">
      <section className="surface settings-card component-version-card">
        <header className="section-head"><div><span className="eyebrow">SYSTEM / VERSIONEN</span><h2>Installierte Komponenten</h2></div><Activity size={19} /></header>
        <dl className="component-versions">
          <div><dt>Dashboard</dt><dd>{DASHBOARD_VERSION}</dd></div>
          <div><dt>Server</dt><dd>{serverVersion || "Nicht erreichbar"}</dd></div>
          <div><dt>Agenten · OS-Profile</dt><dd>{agentVersions.length ? agentVersions.map(([version, count]) => <span key={version}>{version} <small>× {count}</small></span>) : "Keine Agenten"}</dd></div>
        </dl>
        <p>Agenten melden die tatsächlich installierte Payload-Version. Ein neuer Dashboard-Build ändert diese Angaben nicht.</p>
      </section>
      <DashboardUsers token={token} identity={identity} canManage={canManageReleases} />
      <section className="surface settings-card">
        <header className="section-head">
          <div>
            <span className="eyebrow">Darstellung</span>
            <h2>Farbschema</h2>
          </div>
          <Moon size={19} />
        </header>
        <div className="scheme-switch" role="radiogroup" aria-label="Farbschema">
          {THEMES.map((item) => (
            <button
              key={item.id}
              role="radio"
              aria-checked={theme === item.id}
              className={theme === item.id ? "active" : ""}
              onClick={() => onTheme(item.id)}
            >
              {item.name}
            </button>
          ))}
        </div>
      </section>
      {canResetTraffic && <section className="surface settings-card traffic-reset-card">
        <header className="section-head">
          <div>
            <span className="eyebrow">STATISTIKEN</span>
            <h2>Traffic-Statistik</h2>
          </div>
          <Network size={19} />
        </header>
        <p>
          Setzt die sichtbaren Monatswerte für alle Geräte auf jetzt zurück. Rohdaten
          und historische Messwerte bleiben vollständig erhalten.
        </p>
        {trafficResetMessage && <small className="traffic-reset-message">{trafficResetMessage}</small>}
        <button
          className="traffic-reset-button"
          disabled={resettingTraffic}
          onClick={() => {
            if (!window.confirm("Traffic-Statistik jetzt zurücksetzen? Rohdaten bleiben erhalten.")) return;
            setResettingTraffic(true);
            setTrafficResetMessage("");
            void onResetTraffic()
              .then(() => setTrafficResetMessage("Traffic-Statistik wurde zurückgesetzt."))
              .catch(() => setTrafficResetMessage("Zurücksetzen fehlgeschlagen. Bitte erneut versuchen."))
              .finally(() => setResettingTraffic(false));
          }}
        >
          <RefreshCw size={16} /> {resettingTraffic ? "Wird zurückgesetzt …" : "Traffic-Statistik zurücksetzen"}
        </button>
      </section>}
      {canManageReleases && <section className="surface settings-card">
        <header className="section-head"><div><span className="eyebrow">0.6 UPDATE-VERTEILUNG</span><h2>Signierte Payload-Releases</h2></div><Download size={19} /></header>
        <p>Füge ausschließlich das vom Payload-Build erzeugte Manifest ein. Ein Release wird nie automatisch verteilt: Erst die bewusste Freigabe am einzelnen Node stellt es für dessen Core bereit.</p>
        <form className="telegram-settings" onSubmit={(event) => { event.preventDefault(); setReleaseMessage(""); try { const manifest = JSON.parse(releaseManifest) as Record<string, unknown>; void onRegisterRelease(manifest).then(() => { setReleaseManifest(""); setReleaseMessage("Signiertes Release registriert."); }).catch(() => setReleaseMessage("Manifest konnte nicht registriert werden.")); } catch { setReleaseMessage("Das Manifest ist kein gültiges JSON."); } }}>
          <label>Release-Manifest<textarea value={releaseManifest} onChange={(event) => setReleaseManifest(event.target.value)} placeholder='{"schema_version":1,…}' rows={5} /></label>
          {releaseMessage && <small className="traffic-reset-message">{releaseMessage}</small>}
          <button className="primary" type="submit" disabled={!releaseManifest.trim()}>Signiertes Release registrieren</button>
        </form>
        <div className="settings-release-list">{releases.map((release) => <p key={release.release_id}><b>{release.payload_version}</b> · {release.platform}/{release.architecture} · {release.channel.toUpperCase()} · {release.assigned_nodes} freigegeben<br /><code title="Release-ID">{release.release_id}</code></p>)}{!releases.length && <p>Noch kein Release registriert.</p>}</div>
      </section>}
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
                <span className="policy-label">{{ cpu_threshold: "CPU", memory_threshold: "Arbeitsspeicher", gpu_threshold: "GPU", disk_threshold: "Laufwerk" }[key]}</span>
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
      {canManageTelegram && telegramDraft && <section className="surface settings-card telegram-settings-card">
        <header className="section-head">
          <div>
            <span className="eyebrow">BENACHRICHTIGUNGEN</span>
            <h2>Telegram</h2>
          </div>
          <Send size={19} />
        </header>
        <p>{telegramDraft.configured ? "Der Bot ist serverseitig verbunden. Zugangsdaten bleiben geschützt auf dem NCC-Server und sind hier nicht sichtbar." : "Telegram ist auf dem Server noch nicht eingerichtet. Bot-Token und Chat-ID müssen sicher auf dem NCC-Server hinterlegt werden."}</p>
        <form className="telegram-settings" onSubmit={(event) => { event.preventDefault(); setTelegramMessage(""); void onTelegram(telegramDraft).then(() => setTelegramMessage("Telegram-Einstellungen gespeichert.")).catch(() => setTelegramMessage("Speichern fehlgeschlagen.")); }}>
          <label className="telegram-enabled"><input type="checkbox" checked={telegramDraft.enabled} onChange={(event) => setTelegramDraft({ ...telegramDraft, enabled: event.target.checked })} /><span><b>Telegram-Benachrichtigungen aktiv</b><small>Unterbricht den Versand, ohne Bot-Zugangsdaten zu verändern.</small></span></label>
          <label>Überschrift · Warnung<input maxLength={128} value={telegramDraft.warning_title} onChange={(event) => setTelegramDraft({ ...telegramDraft, warning_title: event.target.value })} /></label>
          <label>Überschrift · Kritisch<input maxLength={128} value={telegramDraft.critical_title} onChange={(event) => setTelegramDraft({ ...telegramDraft, critical_title: event.target.value })} /></label>
          <label>Überschrift · Entwarnung<input maxLength={128} value={telegramDraft.resolved_title} onChange={(event) => setTelegramDraft({ ...telegramDraft, resolved_title: event.target.value })} /></label>
          <label>Fußzeile<input maxLength={256} value={telegramDraft.footer} onChange={(event) => setTelegramDraft({ ...telegramDraft, footer: event.target.value })} /><small>Platzhalter: {"{version}"} und {"{time}"}.</small></label>
          {telegramMessage && <small className="traffic-reset-message">{telegramMessage}</small>}
          <div className="telegram-actions"><button className="primary" type="submit">Telegram speichern</button><button type="button" disabled={testingTelegram || !telegramDraft.configured} onClick={() => { setTestingTelegram(true); setTelegramMessage(""); void onTelegramTest().then(() => setTelegramMessage("Testnachricht wurde an Telegram gesendet.")).catch(() => setTelegramMessage("Telegram-Test fehlgeschlagen.")).finally(() => setTestingTelegram(false)); }}><Send size={15} /> {testingTelegram ? "Sende …" : "Testnachricht senden"}</button></div>
        </form>
      </section>}
      <section className="surface settings-card">
        <header className="section-head">
          <div>
            <span className="eyebrow">SICHERHEIT</span>
            <h2>Dashboard-Zugang</h2>
          </div>
          <ShieldCheck size={19} />
        </header>
        <p>
          Melde diese Browser-Sitzung ab, um einen neuen einmaligen Admin-Code
          einzugeben. Der bisherige Zugang auf anderen Geräten bleibt erhalten.
        </p>
        <button className="primary" onClick={onSwitchAccess}>
          <KeyRound size={16} /> Zugang wechseln
        </button>
      </section>
    </div></>
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
      <section className="page-intro enrollment-intro">
        <div>
          <span className="eyebrow">FLEET / ONBOARDING</span>
          <h1>Gerät hinzufügen.</h1>
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
              <span className="eyebrow">Neue Einladung</span>
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
            <span className="eyebrow">Schritt 1 · nur jetzt sichtbar</span>
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
              <span>Schritt 2 · auf dem Zielgerät ausführen</span>
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
            <span className="eyebrow">Browser-Zugang</span>
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
            <span className="eyebrow">Geräte-Pairing</span>
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
            <span className="eyebrow">Einladungen</span>
            <h2>Token-Verwaltung</h2>
          </div>
          <b>
            {invitations.filter((item) => item.status === "ready").length} aktiv
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
    [localError, setLocalError] = useState(false),
    [mode, setMode] = useState<"code" | "account">("code"),
    [username, setUsername] = useState(""),
    [password, setPassword] = useState("");
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLocalError(false);
    if (mode === "account") {
      try {
        const response = await fetch("/api/v1/users/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username: username.trim().toLowerCase(), password }),
        });
        if (!response.ok) throw new Error("LOGIN");
        setPassword("");
        localStorage.removeItem("ncc-dashboard-token");
        onSave("");
      } catch { setLocalError(true); }
      return;
    }
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
        <span className="eyebrow">Geschützter Zugang</span>
        <h1>Willkommen, Commander.</h1>
        <p>{mode === "code" ? "Gib deinen achtstelligen Admin-Code ein. Er wird im Dashboard erzeugt und gewährt den vorgesehenen Zugang." : "Melde dich mit deinem persönlichen NCC-Konto an."}</p>
        <div className="segmented login-methods"><button type="button" className={mode === "code" ? "selected" : ""} onClick={() => { setMode("code"); setLocalError(false); }}>Admin-Code</button><button type="button" className={mode === "account" ? "selected" : ""} onClick={() => { setMode("account"); setLocalError(false); }}>Benutzerkonto</button></div>
        <form onSubmit={(event) => void submit(event)}>
          {mode === "code" ? <label>
            Admin-Code
            <input
              autoFocus
              value={value}
              onChange={(e) => setValue(e.target.value.toUpperCase())}
              autoCapitalize="characters"
              autoComplete="one-time-code"
              placeholder="z. B. AB12CD34"
            />
          </label> : <><label>Benutzername<input autoFocus autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} required /></label><label>Passwort<input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label></>}
          {(error || localError) && (
            <small className="form-error">
              {mode === "code" ? "Der Code wurde nicht akzeptiert oder ist abgelaufen." : "Benutzername oder Passwort wurde nicht akzeptiert."}
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
  const [theme, setTheme] = useState<Theme>(() => {
    const stored = localStorage.getItem("ncc-color-scheme");
    return stored === "light" || stored === "dark" ? stored : "system";
  });
  const [token, setToken] = useState(
    () => localStorage.getItem("ncc-dashboard-token") || "",
  );
  const [authenticated, setAuthenticated] = useState<boolean | null>(null),
    [authError, setAuthError] = useState(false);
  const [connectionOnline, setConnectionOnline] = useState(false);
  const [nodes, setNodes] = useState<Node[]>([]),
    [groups, setGroups] = useState<FleetGroup[]>([]),
    [summary, setSummary] = useState<Summary | null>(null),
    [invitations, setInvitations] = useState<Invitation[]>([]),
    [alerts, setAlerts] = useState<AlertRecord[]>([]),
    [releases, setReleases] = useState<AgentRelease[]>([]),
    [policy, setPolicy] = useState<AlertPolicy | null>(null),
    [telegram, setTelegram] = useState<TelegramSettings | null>(null),
    [selectedId, setSelectedId] = useState(""),
    [points, setPoints] = useState<Telemetry[]>([]),
    [monthlyNetwork, setMonthlyNetwork] = useState<NetworkUsageSummary | null>(null);
  const [dismissedAlertIds, setDismissedAlertIds] = useState<Set<string>>(
    () => new Set(JSON.parse(localStorage.getItem("ncc-dismissed-alerts") || "[]")),
  );
  const [accessRole, setAccessRole] = useState<AccessRole>("beta_tester");
  const [identity, setIdentity] = useState<DashboardUser | null>(null);
  const [serverVersion, setServerVersion] = useState<string | null>(null);
  const [trafficResetRevision, setTrafficResetRevision] = useState(0);
  const [page, setPage] = useState<Page>("fleet"),
    [query, setQuery] = useState(""),
    [loading, setLoading] = useState(true),
    [sidebar, setSidebar] = useState(false),
    [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem("ncc-sidebar-collapsed") === "true");
  const selected =
    nodes.find((node) => node.node_id === selectedId) || nodes[0] || null;
  const activeLoadsRef = useRef(0);
  const configLoadRef = useRef<{ token: string; authEpoch: number } | null>(null);
  const authEpochRef = useRef(0);
  const activeTokenRef = useRef(token);
  activeTokenRef.current = token;
  const telemetryCursorRef = useRef("");
  const telemetryNodeRef = useRef("");
  const telemetryTokenRef = useRef("");
  const loadConfiguration = useCallback(async () => {
    const authEpoch = authEpochRef.current;
    if (configLoadRef.current?.token === token && configLoadRef.current.authEpoch === authEpoch) return;
    const request = { token, authEpoch };
    configLoadRef.current = request;
    try {
      const configuration = await Promise.allSettled([
        getJson<FleetGroup[]>("/api/v1/fleet/groups", token),
        getJson<Summary>("/api/v1/fleet/summary", token),
        getJson<Invitation[]>("/api/v1/agent-invitations", token),
        getJson<AlertPolicy>("/api/v1/fleet/alert-policy", token),
        getJson<TelegramSettings>("/api/v1/fleet/telegram", token),
        getJson<AgentRelease[]>("/api/v1/releases", token),
        getJson<DashboardAccess>("/api/v1/admin-codes/access", token),
        getJson<DashboardUser>("/api/v1/users/me", token),
        getJson<ServerVersion>("/api/v1/version", token),
      ]);
      if (activeTokenRef.current !== token || authEpochRef.current !== authEpoch) return;
      if (configuration.some((result) => result.status === "rejected" && (result.reason as { status?: number }).status === 401)) {
        setAuthenticated(false);
        setAuthError(true);
        setConnectionOnline(false);
        return;
      }
      const [nextGroups, nextSummary, nextInvitations, nextPolicy, nextTelegram, nextReleases, nextAccess, nextIdentity, nextVersion] = configuration;
      if (nextGroups.status === "fulfilled") setGroups(nextGroups.value);
      if (nextSummary.status === "fulfilled") setSummary(nextSummary.value);
      if (nextInvitations.status === "fulfilled") setInvitations(nextInvitations.value);
      if (nextPolicy.status === "fulfilled") setPolicy(nextPolicy.value);
      if (nextTelegram.status === "fulfilled") setTelegram(nextTelegram.value);
      if (nextReleases.status === "fulfilled") setReleases(nextReleases.value);
      if (nextAccess.status === "fulfilled") setAccessRole(nextAccess.value.access_role);
      if (nextIdentity.status === "fulfilled") setIdentity(nextIdentity.value);
      if (nextVersion.status === "fulfilled") setServerVersion(nextVersion.value.version);
    } finally {
      if (configLoadRef.current === request) configLoadRef.current = null;
    }
  }, [token]);
  const load = useCallback(
    async (silent = false, full = true) => {
      if (silent && activeLoadsRef.current > 0) return;
      const authEpoch = authEpochRef.current;
      activeLoadsRef.current += 1;
      if (!silent) setLoading(true);
      if (full) void loadConfiguration();
      try {
        const [nextNodes, nextAlerts] = await Promise.allSettled([
          getJson<Node[]>("/api/v1/fleet/nodes", token),
          getJson<AlertRecord[]>("/api/v1/fleet/alerts", token),
        ]);
        if (activeTokenRef.current !== token || authEpochRef.current !== authEpoch) return;
        if ([nextNodes, nextAlerts].some((result) =>
          result.status === "rejected" && (result.reason as { status?: number }).status === 401
        )) {
          setAuthenticated(false);
          setAuthError(true);
          setConnectionOnline(false);
          return;
        }
        if (nextNodes.status === "rejected" && nextAlerts.status === "rejected") {
          setConnectionOnline(false);
          return;
        }
        if (nextNodes.status === "fulfilled") {
          setNodes(nextNodes.value);
          setSelectedId((current) =>
            nextNodes.value.some((node) => node.node_id === current)
              ? current
              : nextNodes.value[0]?.node_id || "",
          );
        }
        if (nextAlerts.status === "fulfilled") {
          setAlerts(nextAlerts.value);
          const activeAlertIds = new Set(
            nextAlerts.value.filter((alert) => alert.active).map((alert) => alert.alert_id),
          );
          setDismissedAlertIds((current) => {
            const next = new Set([...current].filter((id) => activeAlertIds.has(id)));
            if (next.size === current.size && [...next].every((id) => current.has(id))) return current;
            localStorage.setItem("ncc-dismissed-alerts", JSON.stringify([...next]));
            return next;
          });
        }
        setAuthenticated(true);
        setConnectionOnline(nextNodes.status === "fulfilled");
        setAuthError(false);
      } catch (error) {
        if (activeTokenRef.current !== token || authEpochRef.current !== authEpoch) return;
        setConnectionOnline(false);
        if ((error as Error & { status?: number }).status === 401) {
          setAuthenticated(false);
          setAuthError(true);
        }
      } finally {
        activeLoadsRef.current -= 1;
        if (activeTokenRef.current === token && authEpochRef.current === authEpoch) setLoading(false);
      }
    },
    [token, loadConfiguration],
  );
  useEffect(() => {
    // design.css follows prefers-color-scheme for "system".
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("ncc-color-scheme", theme);
    localStorage.removeItem("ncc-concept-theme");
  }, [theme]);
  useEffect(() => localStorage.setItem("ncc-sidebar-collapsed", String(sidebarCollapsed)), [sidebarCollapsed]);
  useEffect(() => {
    // Stop unauthenticated polling. Returning from cookie login changes
    // authenticated from false to null even when the legacy token stays empty.
    if (authenticated === false) return;
    if (authenticated === null) void load();
    let ticks = 0;
    const poll = window.setInterval(() => {
      if (document.visibilityState !== "visible") return;
      ticks += 1;
      void load(true, ticks % 12 === 0);
    }, 5000);
    const resume = () => {
      if (document.visibilityState === "visible") {
        ticks = 0;
        void load(true, true);
      }
    };
    document.addEventListener("visibilitychange", resume);
    return () => { clearInterval(poll); document.removeEventListener("visibilitychange", resume); };
  }, [load, authenticated]);
  useEffect(() => {
    if (!selected) return;
    const nodeId = selected.node_id;
    if (telemetryNodeRef.current !== nodeId || telemetryTokenRef.current !== token) {
      telemetryNodeRef.current = nodeId;
      telemetryTokenRef.current = token;
      telemetryCursorRef.current = "";
      setPoints([]);
    }
    let current = true;
    const refresh = async () => {
      const cursor = telemetryCursorRef.current;
      const base = `/api/v1/fleet/nodes/${nodeId}/telemetry?limit=120`;
      let incoming: Telemetry[];
      let replace = !cursor;
      try {
        incoming = await getJson<Telemetry[]>(cursor ? `${base}&after=${encodeURIComponent(cursor)}` : base, token);
      } catch (error) {
        if (!cursor || (error as Error & { status?: number }).status !== 404) return;
        // A pruned cursor is recoverable by reading the current chart window.
        try { incoming = await getJson<Telemetry[]>(base, token); }
        catch { return; }
        replace = true;
      }
      if (!current || telemetryNodeRef.current !== nodeId) return;
      if (replace) telemetryCursorRef.current = incoming[incoming.length - 1]?.point_id || "";
      else if (incoming.length) telemetryCursorRef.current = incoming[incoming.length - 1].point_id;
      if (replace) setPoints(incoming);
      else if (incoming.length) setPoints((previous) => {
        const seen = new Set(previous.map((point) => point.point_id));
        return [...previous, ...incoming.filter((point) => !seen.has(point.point_id))].slice(-120);
      });
    };
    void refresh();
    return () => { current = false; };
  }, [selected?.node_id, selected?.latest?.recorded_at, token]);
  useEffect(() => {
    // Monthly totals belong to a specific node. Do not show the previous
    // node's value while its replacement request is still in flight.
    setMonthlyNetwork(null);
    if (!selected) return;
    let current = true;
    const refresh = () => getJson<NetworkUsageSummary>(
      `/api/v1/fleet/nodes/${selected.node_id}/network/month`, token, 90_000,
    ).then((value) => { if (current) setMonthlyNetwork(value); }).catch(() => undefined);
    void refresh();
    const poll = window.setInterval(() => void refresh(), 300_000);
    return () => { current = false; window.clearInterval(poll); };
  }, [selected?.node_id, token, trafficResetRevision]);
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
    authEpochRef.current += 1;
    localStorage.setItem("ncc-dashboard-token", value);
    setToken(value);
    setAccessRole("beta_tester");
    setIdentity(null);
    setConnectionOnline(false);
    setLoading(true);
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
  const saveTelegram = async (nextTelegram: TelegramSettings) => {
    const response = await fetch("/api/v1/fleet/telegram", {
      method: "PUT",
      headers: { ...headers(token), "Content-Type": "application/json" },
      body: JSON.stringify({
        enabled: nextTelegram.enabled,
        warning_title: nextTelegram.warning_title,
        critical_title: nextTelegram.critical_title,
        resolved_title: nextTelegram.resolved_title,
        footer: nextTelegram.footer,
      }),
    });
    if (!response.ok) throw new Error("REQUEST");
    setTelegram((await response.json()) as TelegramSettings);
  };
  const testTelegram = async () => {
    const response = await fetch("/api/v1/fleet/telegram/test", {
      method: "POST",
      headers: headers(token),
    });
    if (!response.ok) throw new Error("REQUEST");
  };
  const resetTrafficStatistics = async () => {
    const response = await fetch("/api/v1/fleet/network/reset", {
      method: "POST",
      headers: headers(token),
    });
    if (!response.ok) throw new Error("REQUEST");
    setMonthlyNetwork(null);
    setTrafficResetRevision((revision) => revision + 1);
  };
  const registerRelease = async (manifest: Record<string, unknown>) => {
    const created = await postJson<AgentRelease>("/api/v1/releases", token, { manifest });
    setReleases((current) => [created, ...current.filter((item) => item.release_id !== created.release_id)]);
  };
  const clearAllAlerts = async () => {
    const response = await fetch("/api/v1/fleet/alerts/clear", { method: "POST", headers: headers(token) });
    if (!response.ok) throw new Error("REQUEST");
    await load(true);
  };
  const switchDashboardAccess = async () => {
    try {
      await fetch("/api/v1/admin-codes/logout", { method: "POST" });
    } finally {
      authEpochRef.current += 1;
      localStorage.removeItem("ncc-dashboard-token");
      setToken("");
      setAccessRole("beta_tester");
      setIdentity(null);
      setConnectionOnline(false);
      setAuthenticated(false);
      setAuthError(false);
    }
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
  const attachProfile = async (deviceId: string, nodeId: string) => {
    const response = await fetch(`/api/v1/fleet/physical-devices/${encodeURIComponent(deviceId)}/nodes/${encodeURIComponent(nodeId)}`, {
      method: "POST", headers: headers(token),
    });
    if (!response.ok) throw new Error("REQUEST");
    const onlineProfile = nodes.find((node) => node.physical_device_id === deviceId && node.online);
    if (onlineProfile) setSelectedId(onlineProfile.node_id);
    await load(false, false);
  };
  const detachProfile = async (deviceId: string, nodeId: string) => {
    const response = await fetch(`/api/v1/fleet/physical-devices/${encodeURIComponent(deviceId)}/nodes/${encodeURIComponent(nodeId)}`, {
      method: "DELETE", headers: headers(token),
    });
    if (!response.ok) throw new Error("REQUEST");
    await load(false, false);
  };
  const canManageAccess = accessRole === "commander";
  if (authenticated === null) return <div className="login"><section><Brand /><span className="eyebrow">NCC-Verbindung</span><h1>{loading ? "Verbindung wird hergestellt." : "NCC-Server nicht erreichbar."}</h1><p>{loading ? "Das Dashboard lädt die aktuellen Fleet-Daten." : "Die Anmeldung wurde nicht zurückgesetzt. Prüfe die Verbindung und versuche es erneut."}</p>{!loading && <button className="primary-button" type="button" onClick={() => void load()}>Erneut verbinden <RefreshCw size={16} /></button>}</section></div>;
  if (authenticated === false)
    return (
      <Login onSave={saveToken} error={authenticated === false && authError} />
    );
  const title =
    page === "fleet"
      ? "Übersicht"
      : page === "explorer"
        ? "Geräte"
      : page === "statistics"
        ? "Statistiken"
        : page === "alerts"
          ? "Warnungen"
          : page === "chat"
            ? "Chat"
          : page === "onboarding"
            ? "Gerät hinzufügen"
            : "Einstellungen";
  const activeAlertCount = alerts.filter((alert) => alert.active).length;
  const navGroups: { label: string; items: { id: Page; label: string; icon: React.ReactNode }[] }[] = [
    { label: "Überwachen", items: [
      { id: "fleet", label: "Übersicht", icon: <LayoutDashboard size={18} /> },
      { id: "explorer", label: "Geräte", icon: <Server size={18} /> },
      { id: "statistics", label: "Statistiken", icon: <BarChart3 size={18} /> },
      { id: "alerts", label: "Warnungen", icon: <AlertTriangle size={18} /> },
    ] },
    { label: "Verwalten", items: [
      { id: "chat", label: "Chat", icon: <MessageSquare size={18} /> },
      { id: "settings", label: "Einstellungen", icon: <Settings size={18} /> },
    ] },
  ];
  return (
    <div className="app-shell ncc-production">
      <aside className={`sidebar ${sidebar ? "open" : ""}`}>
        <div className="brand">
          <div className="brand-mark" aria-hidden="true"><span/><span/><span/><span/></div>
          <div><strong>no0bz</strong><small>Command Center</small></div>
          <button className="mobile-close icon-button" onClick={() => setSidebar(false)} aria-label="Menü schließen"><ConceptIcon name="close" /></button>
        </div>
        <nav aria-label="Hauptnavigation">
          {navGroups.map((group) => (
            <div className="nav-group" key={group.label}>
              <div className="nav-caption">{group.label}</div>
              {group.items.map((item) => (
                <button
                  key={item.id}
                  className={`nav-item ${page === item.id ? "active" : ""}`}
                  aria-current={page === item.id ? "page" : undefined}
                  onClick={() => { setPage(item.id); setSidebar(false); }}
                >
                  {item.icon}<span>{item.label}</span>
                  {item.id === "alerts" && activeAlertCount > 0 && <em aria-label={`${activeAlertCount} aktive Warnungen`}>{activeAlertCount}</em>}
                </button>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="fleet-health">
            <span className={`fleet-health-dot${summary && summary.online_nodes < summary.total_nodes ? " partial" : ""}`} aria-hidden="true" />
            <span><b>{summary?.online_nodes || 0} von {summary?.total_nodes || 0}</b> Geräten online</span>
          </div>
          {canManageAccess && <button className="sidebar-add" type="button" onClick={() => setPage("onboarding")}><ConceptIcon name="plus" size={16} /> Gerät hinzufügen</button>}
          <div className="profile">
            <div className="avatar" aria-hidden="true">{(identity?.username || "C").slice(0, 1).toUpperCase()}</div>
            <div><b>{identity?.username || (canManageAccess ? "Commander" : "Beta-Tester")}</b><small>{canManageAccess ? "Commander" : "Beta-Tester"}</small></div>
          </div>
        </div>
      </aside>
      {sidebar && <div className="scrim" onClick={() => setSidebar(false)} />}
      <div className="main">
        <header className="topbar">
          <div className="top-left">
            <button className="mobile-menu icon-button" onClick={() => setSidebar(true)} aria-label="Menü öffnen"><Menu size={20} /></button>
            <h1 className="page-title">{title}</h1>
          </div>
          <div className="top-actions">
            <span className={`live-pill${connectionOnline ? "" : " disconnected"}`}><i aria-hidden="true"/> {connectionOnline ? "Live" : "Verbindung unterbrochen"}</span>
            <button
              className="top-alert icon-button"
              aria-label={activeAlertCount ? `Warnungen (${activeAlertCount} aktiv)` : "Warnungen"}
              title="Warnungen"
              onClick={() => setPage("alerts")}
            >
              <ConceptIcon name="alert" size={19} />
              {activeAlertCount > 0 && <i />}
            </button>
            <button
              className="icon-button"
              onClick={() => void load()}
              aria-label="Daten neu laden"
              title="Daten neu laden"
            >
              <RefreshCw size={17} className={loading ? "spin" : ""} />
            </button>
          </div>
        </header>
        <main className="content">
          {page === "fleet" ? (
            <CommandOverviewExact
              nodes={nodes}
              selected={selected}
              onSelect={setSelectedId}
              points={points}
              alerts={alerts}
              dismissedAlerts={dismissedAlertIds}
              onOpenAlerts={() => setPage("alerts")}
              onOpenExplorer={() => setPage("explorer")}
              token={token}
            />
          ) : page === "explorer" ? (
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
              onAttachProfile={attachProfile}
              onDetachProfile={detachProfile}
              canDelete={canManageAccess}
              releases={releases}
              token={token}
              dismissedAlerts={dismissedAlertIds}
              onDismissAlert={dismissAlert}
              onAddDevice={() => setPage("onboarding")}
            />
          ) : page === "statistics" ? (
            <StatisticsPage nodes={nodes} summary={summary} token={token} trafficResetRevision={trafficResetRevision} canManage={canManageAccess} />
          ) : page === "alerts" ? (
            <AlertsPage alerts={alerts} canClear={canManageAccess} onClear={clearAllAlerts} />
          ) : page === "chat" ? (
            <FleetChat key={`${identity?.user_id || identity?.username || "anonymous"}:${token}`} token={token} identity={identity} />
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
              serverVersion={serverVersion}
              nodes={nodes}
              onTheme={setTheme}
              onSwitchAccess={() => void switchDashboardAccess()}
              policy={policy}
              onPolicy={savePolicy}
              telegram={telegram}
              onTelegram={saveTelegram}
              onTelegramTest={testTelegram}
              canManageTelegram={canManageAccess}
              canResetTraffic={canManageAccess}
              onResetTraffic={resetTrafficStatistics}
              releases={releases}
              onRegisterRelease={registerRelease}
              canManageReleases={canManageAccess}
              token={token}
              identity={identity}
            />
          )}
        </main>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
