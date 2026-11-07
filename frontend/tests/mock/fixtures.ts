/* Fixture data shaped exactly like the backend schemas (schemas.py). */
import type {
  AccountInvite, AdminCode, AgentInvitation, AgentPairing, AgentRelease, AlertPolicy, ChatMessage,
  DashboardUser, FleetAlert, FleetGroup, FleetNode, Game, Metrics, PhysicalDevice, PlaytimeStats, HardwareStats,
  TelegramSettings,
} from "../../src/api/types.ts";

const minute = 60_000;
export const iso = (offsetMs = 0) => new Date(Date.now() + offsetMs).toISOString();

function metrics(seed: number, extra: Partial<Metrics> = {}): Metrics {
  const wave = Math.sin(Date.now() / 20_000 + seed) * 8;
  return {
    cpu: { percent: 22 + seed * 7 + wave, model: seed % 2 ? "AMD Ryzen 7 7800X3D" : "Intel Core i7-13700K", logical_cores: 16, physical_cores: 8, frequency_mhz: 4700, temperature_c: 54 + seed * 3, power_w: 48 + seed * 9 },
    memory: { percent: 41 + seed * 6, used_gb: 13.1 + seed, total_gb: 32, available_gb: 18 },
    gpus: [{ index: 0, name: seed % 2 ? "NVIDIA GeForce RTX 4070 Super" : "AMD Radeon RX 7800 XT", percent: 30 + seed * 9 + wave, vram_percent: 48, vram_used_gb: 5.8, vram_total_gb: 12, temperature_c: 58 + seed * 4, power_w: 140 + seed * 20 }],
    lhm_gpus: [{ index: 0, name: seed % 2 ? "NVIDIA GeForce RTX 4070 Super" : "AMD Radeon RX 7800 XT", temperature_c: 58 + seed * 4, hotspot_temperature_c: 71 + seed * 4, power_w: 140 + seed * 20, fan_rpm: 1350 }],
    network: { download_mbps: Math.max(0, 18 + seed * 11 + wave * 3), upload_mbps: Math.max(0, 2.4 + seed + wave / 4), bytes_recv: 9_812_345_678, bytes_sent: 1_234_567_890, interface: "Ethernet" },
    disks: [
      { name: "C:", mount: "C:\\", filesystem: "NTFS", percent: 61, used_gb: 570, total_gb: 931, read_mbps: 1.2, write_mbps: 0.4 },
      { name: "D:", mount: "D:\\", filesystem: "NTFS", percent: 83, used_gb: 1540, total_gb: 1863, read_mbps: 0, write_mbps: 0 },
    ],
    hardware: {
      provider: "librehardwaremonitor",
      pawnio: "running",
      components: { board: "MSI MAG B650 Tomahawk WiFi" },
      board: {
        chip: "Nuvoton NCT6687D",
        fans: [{ label: "Fan #1", rpm: 980 }, { label: "Fan #2", rpm: 1210 }, { label: "Fan #3", rpm: 0 }],
        temperatures: [{ label: "Temperature #1", value: 38 }, { label: "Temperature #2", value: 44 }],
      },
      memory_modules: [{ name: "DIMM A2", temperature_c: 41 }, { name: "DIMM B2", temperature_c: 42 }],
      storage: [{ name: "Samsung 990 Pro 1TB", temperature_c: 46 }],
    },
    processes: [{ pid: 4312, name: "game.exe", cpu: 31.5, memory: 18.2 }, { pid: 1200, name: "discord.exe", cpu: 2.1, memory: 3.4 }],
    system: { hostname: "rig", platform: "Windows-11-10.0.26300-SP0", boot_time: Date.now() / 1000 - 86400 },
    ...extra,
  };
}

function node(partial: Partial<FleetNode> & Pick<FleetNode, "node_id" | "display_name">, seed: number, online = true): FleetNode {
  return {
    machine_id: `machine-${partial.node_id}`,
    platform: "windows",
    approved: true,
    access_role: "commander",
    online,
    agent_version: "0.6.1",
    metadata: {},
    created_at: iso(-40 * 86400_000),
    last_seen_at: online ? iso(-3000) : iso(-3 * 86400_000),
    availability_percent: 97.4,
    availability_started_at: iso(-40 * 86400_000),
    uptime_record_seconds: 5 * 86400,
    gaming_mode_until: null,
    auto_gaming_until: null,
    game_tracking: "titles",
    auto_gaming_mode: true,
    now_playing: null,
    sensor_labels: {},
    owner_user_id: null,
    owner_name: null,
    update_check_requested_at: null,
    physical_device_id: null,
    physical_device_name: null,
    fleet_group_id: "g-gaming",
    fleet_position: seed,
    update_channel: "stable",
    pending_release_id: null,
    release_allow_downgrade: false,
    release_target_version: null,
    release_pin_held_back: false,
    latest: online ? { point_id: `p-${partial.node_id}`, sample_id: null, recorded_at: iso(-3000), metrics: metrics(seed) } : null,
    ...partial,
  };
}

export function createFixtures() {
  const groups: FleetGroup[] = [
    { group_id: "g-gaming", name: "Gaming-PCs", position: 0 },
    { group_id: "default-servers", name: "Server", position: 1 },
    { group_id: "g-mobile", name: "Laptops", position: 2 },
  ];
  const nodes: FleetNode[] = [
    node({
      node_id: "n-rig-win", display_name: "Brunzel-Rig", physical_device_id: "d-rig", physical_device_name: "Brunzel-Rig",
      now_playing: { session_id: "s1", game_id: "game-drg", title: "Deep Rock Galactic", launcher: "steam", started_at: iso(-47 * minute), has_artwork: true, genres: ["Action", "Co-op"] },
      sensor_labels: { "fan:Fan #1": { name: "CPU-Kühler", role: "cpu" } }, owner_user_id: "u-bruno", owner_name: "bruno",
    }, 0),
    node({ node_id: "n-rig-cachy", display_name: "Brunzel-Rig CachyOS", platform: "linux", physical_device_id: "d-rig", physical_device_name: "Brunzel-Rig", update_channel: "beta" }, 1, false),
    node({ node_id: "n-kalle", display_name: "Kalle-PC", owner_user_id: "u-kalle", owner_name: "kalle", access_role: "beta_tester" }, 3),
    node({ node_id: "n-mia", display_name: "Mia-Box", platform: "linux", gaming_mode_until: iso(95 * minute), owner_user_id: "u-mia", owner_name: "mia", access_role: "beta_tester" }, 2),
    node({
      node_id: "n-tower", display_name: "Tower", platform: "linux", machine_id: "unraid:tower", metadata: { source: "unraid-api" }, fleet_group_id: "default-servers", agent_version: "6.12.13",
      latest: { point_id: "p-tower", sample_id: null, recorded_at: iso(-8000), metrics: {
        cpu: { percent: 12, model: "Intel Core i5-12400", logical_cores: 12, temperature_c: 41 },
        memory: { percent: 63, total_gb: 64, used_gb: 40.3 },
        network: { download_mbps: 4.2, upload_mbps: 31.7 },
        disks: [
          { name: "Cache", percent: 38, total_gb: 1000, used_gb: 380, temperature_c: 39, status: "DISK_OK", spinning: true },
          { name: "Disk 1", percent: 71, total_gb: 12000, used_gb: 8520, temperature_c: 34, status: "DISK_OK", spinning: true },
          { name: "Disk 2", percent: 66, total_gb: 12000, used_gb: 7920, temperature_c: null, status: "DISK_OK", spinning: false },
        ],
        containers: [{ names: ["plex"], state: "RUNNING" }, { names: ["nextcloud"], state: "RUNNING" }, { names: ["minecraft"], state: "EXITED" }],
        vms: [{ name: "HomeAssistant", state: "RUNNING" }],
        unraid: { api_connected: true, version: "6.12.13", array_state: "STARTED" },
      } },
    }, 4),
    node({ node_id: "n-lappi", display_name: "Lappi", fleet_group_id: "g-mobile", agent_version: "0.5.9" }, 5, false),
  ];
  const physical: PhysicalDevice[] = [{ device_id: "d-rig", display_name: "Brunzel-Rig", node_ids: ["n-rig-win", "n-rig-cachy"] }];
  const alerts: FleetAlert[] = [
    { alert_id: "a1", node_id: "n-kalle", display_name: "Kalle-PC", kind: "gpu_temperature", severity: "warning", active: true, message: "GPU-Temperatur bei 87 °C (Grenze 85 °C).", opened_at: iso(-12 * minute), updated_at: iso(-minute), resolved_at: null },
    { alert_id: "a2", node_id: "n-tower", display_name: "Tower", kind: "disk", severity: "critical", active: true, message: "Tower: Laufwerk-Auslastung bei 96 % (critical).", opened_at: iso(-3 * 3600_000), updated_at: iso(-minute), resolved_at: null },
    { alert_id: "a3", node_id: "n-mia", display_name: "Mia-Box", kind: "cpu", severity: "warning", active: false, message: "Mia-Box: CPU-Auslastung bei 93 % (warning).", opened_at: iso(-26 * 3600_000), updated_at: iso(-25 * 3600_000), resolved_at: iso(-25 * 3600_000) },
  ];
  const games: Game[] = [
    { game_id: "game-drg", title: "Deep Rock Galactic", launcher: "steam", steam_app_id: 548430, match_state: "matched", manual_match: false, store_name: "Deep Rock Galactic", description: "Zwergen-Koop im Bergwerk.", genres: ["Action", "Co-op"], developers: ["Ghost Ship Games"], release_date: "13 May, 2020", has_artwork: true, artwork_source: "steam" },
    { game_id: "game-factorio", title: "Factorio", launcher: "steam", steam_app_id: 427520, match_state: "matched", manual_match: false, store_name: "Factorio", description: "Fabriken bauen.", genres: ["Strategy"], developers: ["Wube Software"], release_date: "14 Aug, 2020", has_artwork: false, artwork_source: null },
    { game_id: "game-wow", title: "World of Warcraft", launcher: "battlenet", steam_app_id: null, match_state: "unmatched", manual_match: false, store_name: null, description: null, genres: [], developers: [], release_date: null, has_artwork: false, artwork_source: null },
  ];
  const stats: PlaytimeStats = {
    days: 30, total_seconds: 151_200, session_count: 41, game_count: 3,
    longest_session: { title: "Factorio", node_name: "Mia-Box", seconds: 21_600, started_at: iso(-6 * 86400_000) },
    games: [
      { game_id: "game-factorio", title: "Factorio", launcher: "steam", has_artwork: false, custom_artwork: false, genres: ["Strategy"], seconds: 72_000, sessions: 12, last_played_at: iso(-86400_000), hardware: { cpu_percent: { average: 41, max: 88 }, gpu_temperature_c: { average: 61, max: 70 } }, energy_wh: 3400 },
      { game_id: "game-drg", title: "Deep Rock Galactic", launcher: "steam", has_artwork: true, custom_artwork: false, genres: ["Action"], seconds: 54_000, sessions: 20, last_played_at: iso(-47 * minute), hardware: { gpu_percent: { average: 77, max: 99 }, gpu_temperature_c: { average: 71, max: 80 } }, energy_wh: 5100 },
      { game_id: "game-wow", title: "World of Warcraft", launcher: "battlenet", has_artwork: false, custom_artwork: false, genres: [], seconds: 25_200, sessions: 9, last_played_at: iso(-3 * 86400_000), hardware: {}, energy_wh: 1200 },
    ],
    nodes: [{ node_id: "n-rig-win", display_name: "Brunzel-Rig", seconds: 70_000 }, { node_id: "n-mia", display_name: "Mia-Box", seconds: 52_000 }, { node_id: "n-kalle", display_name: "Kalle-PC", seconds: 29_200 }],
    daily: Array.from({ length: 30 }, (_, index) => ({ date: new Date(Date.now() - (29 - index) * 86400_000).toISOString().slice(0, 10), seconds: Math.round(Math.abs(Math.sin(index * 1.7)) * 14_000) })),
    heatmap: Array.from({ length: 7 }, (_, day) => Array.from({ length: 24 }, (_, hour) => (hour >= 18 && hour <= 23 ? Math.round(2500 + Math.abs(Math.sin(day + hour)) * 3000) : hour >= 14 && day >= 5 ? 1500 : 0))),
    recent_sessions: [
      { session_id: "s1", game_id: "game-drg", title: "Deep Rock Galactic", node_name: "Brunzel-Rig", started_at: iso(-47 * minute), ended_at: iso(-minute), seconds: 2760 },
      { session_id: "s2", game_id: "game-factorio", title: "Factorio", node_name: "Mia-Box", started_at: iso(-30 * 3600_000), ended_at: iso(-26 * 3600_000), seconds: 14_400 },
    ],
  };
  const hardware: HardwareStats = {
    days: 30,
    metrics: ["cpu_percent", "cpu_temperature_c", "cpu_power_w", "gpu_percent", "gpu_temperature_c", "gpu_hotspot_c", "gpu_power_w", "memory_percent", "drive_temperature_c", "cpu_fan_rpm"],
    summary: { cpu_percent: { average: 27.4, max: 98 }, cpu_temperature_c: { average: 55.1, max: 88 }, cpu_power_w: { average: 61, max: 142 }, gpu_percent: { average: 33, max: 100 }, gpu_temperature_c: { average: 59, max: 84 }, gpu_hotspot_c: { average: 72, max: 97 }, gpu_power_w: { average: 120, max: 287 }, memory_percent: { average: 48, max: 91 }, drive_temperature_c: { average: 41, max: 58 }, cpu_fan_rpm: { average: 1010, max: 1890 } },
    records: { cpu_temperature_c: { value: 88, at: iso(-5 * 86400_000), node_name: "Kalle-PC" }, gpu_hotspot_c: { value: 97, at: iso(-2 * 86400_000), node_name: "Brunzel-Rig" }, gpu_power_w: { value: 287, at: iso(-2 * 86400_000), node_name: "Brunzel-Rig" } },
    energy_wh: 48_200,
    daily: Array.from({ length: 30 }, (_, index) => ({ date: new Date(Date.now() - (29 - index) * 86400_000).toISOString().slice(0, 10), energy_wh: Math.round(900 + Math.abs(Math.sin(index)) * 2400), metrics: { cpu_temperature_c: { average: 50 + (index % 7), max: 70 + (index % 9) }, gpu_temperature_c: { average: 55 + (index % 5), max: 75 + (index % 8) } } })),
    hours_covered: 640,
  };
  const users: DashboardUser[] = [
    { user_id: "u-bruno", username: "bruno", role: "commander", active: true, managed: true, created_at: iso(-90 * 86400_000), full_statistics: false, device_count: 1 },
    { user_id: "u-kalle", username: "kalle", role: "beta_tester", active: true, managed: true, created_at: iso(-50 * 86400_000), full_statistics: false, device_count: 1 },
    { user_id: "u-mia", username: "mia", role: "friend", active: true, managed: true, created_at: iso(-20 * 86400_000), full_statistics: true, device_count: 1 },
    { user_id: "u-old", username: "altkonto", role: "friend", active: false, managed: true, created_at: iso(-200 * 86400_000), full_statistics: false, device_count: 0 },
  ];
  const invites: AccountInvite[] = [
    { invite_id: "i1", label: "Für Jonas", created_at: iso(-86400_000), expires_at: iso(6 * 86400_000), status: "open", used_by: null },
    { invite_id: "i2", label: "Mia", created_at: iso(-20 * 86400_000), expires_at: iso(-13 * 86400_000), status: "used", used_by: "mia" },
  ];
  const pairings: AgentPairing[] = [
    { pairing_id: "pair-waiting-123456", display_name: "Jonas-PC", platform: "windows", access_role: "beta_tester", status: "waiting", created_at: iso(-2 * minute), expires_at: iso(13 * minute) },
    { pairing_id: "pair-approved-12345", display_name: "Mia-Box", platform: "linux", access_role: "beta_tester", status: "approved", created_at: iso(-9 * minute), expires_at: iso(6 * minute) },
    { pairing_id: "pair-claimed-123456", display_name: "Kalle-PC", platform: "windows", access_role: "beta_tester", status: "claimed", created_at: iso(-2 * 86400_000), expires_at: iso(-2 * 86400_000 + 15 * minute) },
  ];
  const agentInvitations: AgentInvitation[] = [
    { token_id: "t1", name: "Kalle-PC", access_role: "commander", status: "bound", node_id: "n-kalle", node_name: "Kalle-PC", created_at: iso(-50 * 86400_000), expires_at: null, last_used_at: iso(-3000), revoked_at: null },
    { token_id: "t2", name: "Ersatz-Laptop", access_role: "beta_tester", status: "ready", node_id: null, node_name: null, created_at: iso(-3600_000), expires_at: iso(7 * 86400_000), last_used_at: null, revoked_at: null },
  ];
  const adminCodes: AdminCode[] = [
    { code_id: "c1", label: "Kalle Handy", status: "used", created_at: iso(-86400_000), expires_at: iso(-86400_000 + 15 * minute), used_at: iso(-86400_000 + 2 * minute), revoked_at: null, access_role: "beta_tester" },
    { code_id: "c2", label: "Notfall", status: "ready", created_at: iso(-5 * minute), expires_at: iso(10 * minute), used_at: null, revoked_at: null, access_role: "commander" },
  ];
  const releases: AgentRelease[] = [
    { release_id: "r-061-win", payload_version: "0.6.1", channel: "stable", platform: "windows", architecture: "x86_64", artifact_url: "https://github.com/example/ncc/releases/download/v0.6.1/payload-windows.zip", sha256: "9f2c".padEnd(64, "a"), size_bytes: 48_211_000, signature_key_id: "ncc-2026", signature_value: "sig", minimum_core_version: "0.6.0", released_at: iso(-10 * 86400_000), assigned_nodes: 1 },
    { release_id: "r-062b-lin", payload_version: "0.6.2-beta.1", channel: "beta", platform: "linux", architecture: "x86_64", artifact_url: "https://github.com/example/ncc/releases/download/v0.6.2-beta.1/payload-linux.tar.gz", sha256: "1b7e".padEnd(64, "b"), size_bytes: 39_004_000, signature_key_id: "ncc-2026", signature_value: "sig", minimum_core_version: null, released_at: iso(-2 * 86400_000), assigned_nodes: 0 },
  ];
  const chat: ChatMessage[] = Array.from({ length: 64 }, (_, index) => ({
    message_id: `m-${String(index).padStart(3, "0")}`,
    sender_node_id: null,
    sender_user_id: index % 3 === 0 ? "u-kalle" : "u-bruno",
    sender_name: index % 3 === 0 ? "kalle" : "bruno",
    body: index === 63 ? "Wer ist heute Abend bei **Deep Rock** dabei?\n\n- Start 20 Uhr\n- Discord wie immer" : `Nachricht Nummer ${index + 1}`,
    body_format: index === 63 ? "markdown" : "plain",
    attachment: index === 60 ? { name: "screenshot.png", content_type: "image/png", size: 182_000, url: "/api/v1/fleet/chat/messages/m-060/attachment" } : null,
    created_at: iso((index - 64) * 7 * minute),
  }));
  const policy: AlertPolicy = { cpu_threshold: 90, memory_threshold: 90, gpu_threshold: 95, disk_threshold: 90, cpu_temperature_threshold: 90, gpu_temperature_threshold: 85, drive_temperature_threshold: 65 };
  const telegram: TelegramSettings = { configured: true, enabled: true, warning_title: "⚠️ NCC-Warnung", critical_title: "🚨 NCC kritisch", resolved_title: "✅ NCC wieder ok", footer: "no0bz Command Center" };
  return { groups, nodes, physical, alerts, games, stats, hardware, users, invites, pairings, agentInvitations, adminCodes, releases, chat, policy, telegram };
}

export type Fixtures = ReturnType<typeof createFixtures>;
