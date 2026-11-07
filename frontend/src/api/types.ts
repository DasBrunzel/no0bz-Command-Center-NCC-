/**
 * Types derived from backend/ncc_server/schemas.py and the routers under
 * backend/ncc_server/api/v1. Datetimes arrive as ISO strings.
 */

export type ISODate = string;
export type AccessRole = "commander" | "beta_tester";
export type DashboardRole = AccessRole | "friend";
export type UpdateChannel = "beta" | "stable";
export type GameTracking = "off" | "presence" | "titles";
export type SensorRole = "cpu" | "case" | "gpu" | "pump" | "radiator";

/** Free-form agent metrics. Only the parts the dashboard reads are typed. */
export interface Metrics {
  cpu?: {
    percent?: number | null;
    per_core?: number[];
    frequency_mhz?: number | null;
    physical_cores?: number | null;
    logical_cores?: number | null;
    threads?: number | null;
    model?: string | null;
    temperature_c?: number | null;
    power_w?: number | null;
  };
  memory?: { percent?: number | null; used_gb?: number | null; available_gb?: number | null; total_gb?: number | null; free_gb?: number | null };
  swap?: { percent?: number | null; used_gb?: number | null; total_gb?: number | null };
  disks?: Array<{
    name?: string;
    mount?: string;
    filesystem?: string;
    fstype?: string;
    percent?: number | null;
    used_gb?: number | null;
    total_gb?: number | null;
    read_mbps?: number | null;
    write_mbps?: number | null;
    temperature_c?: number | null;
    status?: string | null;
    spinning?: boolean | null;
  }>;
  network?: NetworkMetrics | null;
  gpus?: Array<GpuMetrics>;
  lhm_gpus?: Array<GpuMetrics & { hotspot_temperature_c?: number | null; memory_temperature_c?: number | null; fan_rpm?: number | null; frequency_mhz?: number | null }>;
  battery?: { percent?: number; plugged?: boolean; seconds_left?: number } | null;
  processes?: Array<{ pid: number; name: string; cpu: number; memory: number }>;
  system?: { hostname?: string; platform?: string; boot_time?: number };
  hardware?: {
    provider?: string;
    pawnio?: string;
    components?: { board?: string; [key: string]: unknown };
    board?: { chip?: string | null; fans?: Array<{ label: string; rpm?: number | null; control_percent?: number | null }>; temperatures?: Array<{ label: string; value?: number | null }> };
    memory_modules?: Array<{ name?: string; slot?: string; temperature_c?: number | null }>;
    storage?: Array<{ name?: string; temperature_c?: number | null }>;
    temperatures?: Array<{ chip?: string; label?: string; celsius?: number | null }>;
    fans?: Array<{ chip?: string; label?: string; rpm?: number | null }>;
    powers?: Array<{ chip?: string; label?: string; watts?: number | null }>;
    [key: string]: unknown;
  };
  vms?: Array<{ name?: string; state?: string; [key: string]: unknown }>;
  containers?: Array<{ name?: string; names?: string[]; state?: string; status?: string; [key: string]: unknown }>;
  unraid?: { api_connected?: boolean; version?: string; array_state?: string | null };
  [key: string]: unknown;
}

export interface NetworkMetrics {
  bytes_sent?: number;
  bytes_recv?: number;
  total_sent_gb?: number;
  total_recv_gb?: number;
  download_mbps?: number | null;
  upload_mbps?: number | null;
  interface?: string | null;
  errors?: number;
  drops?: number;
}

export interface GpuMetrics {
  index?: number;
  name?: string;
  model?: string;
  percent?: number | null;
  vram_percent?: number | null;
  vram_used_gb?: number | null;
  vram_total_gb?: number | null;
  temperature_c?: number | null;
  power_w?: number | null;
  fan_percent?: number | null;
  source?: string;
}

export interface FleetTelemetryPoint {
  point_id: string;
  sample_id: string | null;
  recorded_at: ISODate;
  metrics: Metrics;
}

export interface NowPlaying {
  session_id: string;
  game_id: string | null;
  title: string | null;
  launcher: string | null;
  started_at: ISODate;
  has_artwork: boolean;
  genres: string[];
}

export interface SensorLabel {
  name: string | null;
  role: SensorRole | null;
}

export interface FleetNode {
  node_id: string;
  machine_id: string;
  display_name: string;
  platform: string;
  approved: boolean;
  access_role: AccessRole;
  online: boolean;
  agent_version: string | null;
  metadata: Record<string, unknown>;
  created_at: ISODate;
  last_seen_at: ISODate | null;
  availability_percent: number;
  availability_started_at: ISODate | null;
  uptime_record_seconds: number;
  gaming_mode_until: ISODate | null;
  auto_gaming_until: ISODate | null;
  game_tracking: GameTracking;
  auto_gaming_mode: boolean;
  now_playing: NowPlaying | null;
  sensor_labels: Record<string, SensorLabel>;
  owner_user_id: string | null;
  owner_name: string | null;
  update_check_requested_at: ISODate | null;
  physical_device_id: string | null;
  physical_device_name: string | null;
  fleet_group_id: string;
  fleet_position: number;
  update_channel: UpdateChannel;
  pending_release_id: string | null;
  release_allow_downgrade: boolean;
  release_target_version: string | null;
  release_pin_held_back: boolean;
  latest: FleetTelemetryPoint | null;
}

export interface FleetGroup {
  group_id: string;
  name: string;
  position: number;
}

export interface FleetNetwork {
  minutes: number;
  bucket_seconds: number;
  online_nodes: number;
  download_mbps: number;
  upload_mbps: number;
  nodes: Array<{ node_id: string; display_name: string; download_mbps: number; upload_mbps: number }>;
  history: Array<{ at: ISODate; download_mbps: number; upload_mbps: number; nodes: number }>;
}

export interface PhysicalDevice {
  device_id: string;
  display_name: string;
  node_ids: string[];
}

export interface FleetLayoutPlacement {
  node_id: string;
  group_id: string;
  position: number;
}

export interface FleetSummary {
  total_nodes: number;
  online_nodes: number;
  offline_nodes: number;
  pending_nodes: number;
  telemetry_points: number;
  server_time: ISODate;
}

export interface FleetAlert {
  alert_id: string;
  node_id: string;
  display_name: string;
  kind: string;
  severity: "warning" | "critical";
  active: boolean;
  message: string;
  opened_at: ISODate;
  updated_at: ISODate;
  resolved_at: ISODate | null;
}

export interface AlertPolicy {
  cpu_threshold: number;
  memory_threshold: number;
  gpu_threshold: number;
  disk_threshold: number;
  cpu_temperature_threshold: number;
  gpu_temperature_threshold: number;
  drive_temperature_threshold: number;
}

export interface NetworkUsageSummary {
  period_start: ISODate;
  received_bytes: number;
  sent_bytes: number;
  samples: number;
  available: boolean;
}

export interface NetworkHistorySample {
  recorded_at: ISODate;
  network: NetworkMetrics | null;
}

export interface TelegramSettings {
  configured: boolean;
  enabled: boolean;
  warning_title: string;
  critical_title: string;
  resolved_title: string;
  footer: string;
}
export type TelegramSettingsUpdate = Omit<TelegramSettings, "configured">;

export interface TelegramAccount {
  available: boolean;
  linked: boolean;
  telegram_name: string | null;
  weekly_recap: boolean;
  bot_username: string | null;
}

export interface TelegramLinkCode {
  code: string;
  expires_at: ISODate;
  deep_link: string | null;
}

export interface Game {
  game_id: string;
  title: string;
  launcher: string;
  steam_app_id: number | null;
  match_state: string;
  manual_match: boolean;
  store_name: string | null;
  description: string | null;
  genres: string[];
  developers: string[];
  release_date: string | null;
  has_artwork: boolean;
  artwork_source: string | null;
}

export interface MetricSummary {
  average: number;
  max: number;
}

/** game_service.playtime_statistics */
export interface PlaytimeStats {
  days: number;
  total_seconds: number;
  session_count: number;
  game_count: number;
  longest_session: { title: string | null; node_name: string | null; seconds: number; started_at: ISODate } | null;
  games: Array<{
    game_id: string | null;
    title: string | null;
    launcher: string | null;
    has_artwork: boolean;
    custom_artwork: boolean;
    genres: string[];
    seconds: number;
    sessions: number;
    last_played_at: ISODate;
    hardware: Record<string, MetricSummary>;
    energy_wh: number;
  }>;
  nodes: Array<{ node_id: string; display_name: string; seconds: number }>;
  daily: Array<{ date: string; seconds: number }>;
  /** 7 rows (Monday first) × 24 hours, seconds played. */
  heatmap: number[][];
  recent_sessions: Array<{
    session_id: string;
    game_id: string | null;
    title: string | null;
    node_name: string;
    started_at: ISODate;
    ended_at: ISODate;
    seconds: number;
  }>;
}

export type HardwareMetricName =
  | "cpu_percent" | "cpu_temperature_c" | "cpu_power_w" | "cpu_fan_rpm"
  | "gpu_percent" | "gpu_temperature_c" | "gpu_hotspot_c" | "gpu_power_w"
  | "memory_percent" | "ram_temperature_c" | "drive_temperature_c" | "case_fan_rpm";

/** hardware_stats.hardware_statistics */
export interface HardwareStats {
  days: number;
  metrics: HardwareMetricName[];
  summary: Partial<Record<HardwareMetricName, MetricSummary>>;
  records: Partial<Record<HardwareMetricName, { value: number; at: ISODate; node_name: string | null }>>;
  energy_wh: number;
  daily: Array<{ date: string; energy_wh: number; metrics: Partial<Record<HardwareMetricName, MetricSummary>> }>;
  hours_covered: number;
}

export interface AgentRelease {
  release_id: string;
  payload_version: string;
  channel: UpdateChannel;
  platform: "windows" | "linux";
  architecture: string;
  artifact_url: string;
  sha256: string;
  size_bytes: number;
  signature_key_id: string;
  signature_value: string;
  minimum_core_version: string | null;
  released_at: ISODate;
  assigned_nodes: number;
}

export interface ReleaseFeedStatus {
  enabled: boolean;
  repository: string;
  checked_at: ISODate | null;
  error: string | null;
  registered: string[];
}

export interface ChatAttachment {
  name: string;
  content_type: string;
  size: number;
  url: string;
}

export interface ChatMessage {
  message_id: string;
  sender_node_id: string | null;
  sender_user_id: string | null;
  sender_name: string;
  body: string;
  body_format: "plain" | "markdown";
  attachment: ChatAttachment | null;
  created_at: ISODate;
}

export interface ChatParticipant {
  user_id: string | null;
  display_name: string;
  role: DashboardRole;
}

export interface AgentInvitation {
  token_id: string;
  name: string;
  access_role: AccessRole;
  status: "ready" | "bound" | "expired" | "revoked";
  node_id: string | null;
  node_name: string | null;
  created_at: ISODate;
  expires_at: ISODate | null;
  last_used_at: ISODate | null;
  revoked_at: ISODate | null;
}
export interface AgentInvitationCreated extends AgentInvitation {
  token: string;
}

export interface AdminCode {
  code_id: string;
  label: string;
  status: "ready" | "used" | "expired" | "revoked";
  created_at: ISODate;
  expires_at: ISODate;
  used_at: ISODate | null;
  revoked_at: ISODate | null;
  access_role: AccessRole;
}
export interface AdminCodeCreated {
  code: string;
  expires_at: ISODate;
  access_role: AccessRole;
}

export interface DashboardAccess {
  access_role: DashboardRole;
}

export interface DashboardUser {
  user_id: string | null;
  username: string;
  role: DashboardRole;
  active: boolean;
  managed: boolean;
  created_at?: ISODate | null;
  full_statistics: boolean;
  device_count: number;
}

export interface AccountInvite {
  invite_id: string;
  label: string;
  created_at: ISODate;
  expires_at: ISODate;
  status: "open" | "used" | "expired" | "revoked";
  used_by: string | null;
}
export interface AccountInviteCreated extends AccountInvite {
  code: string;
}

export interface AgentPairing {
  pairing_id: string;
  display_name: string;
  platform: string;
  access_role: AccessRole;
  status: "waiting" | "approved" | "claimed" | "expired" | "cancelled";
  created_at: ISODate;
  expires_at: ISODate;
}

export interface ArtworkCandidate {
  index: number;
  game_name: string;
  width: number | null;
  height: number | null;
  style: string | null;
  preview_url: string;
}

export interface ServerVersion {
  version: string;
  api: string;
}
