import type { FleetAlert, FleetNode, Metrics, PhysicalDevice } from "../api/types";
import { num } from "./format";

export type LampState = "go" | "caution" | "stop" | "shunt" | "off";

export function gamingUntil(node: FleetNode, now = Date.now()): string | null {
  const manual = node.gaming_mode_until && new Date(node.gaming_mode_until).getTime() > now ? node.gaming_mode_until : null;
  const auto = node.auto_gaming_until && new Date(node.auto_gaming_until).getTime() > now ? node.auto_gaming_until : null;
  if (manual && auto) return new Date(manual) > new Date(auto) ? manual : auto;
  return manual ?? auto;
}

export function isUnraid(node: FleetNode): boolean {
  return node.machine_id.startsWith("unraid:") || node.metadata?.source === "unraid-api" || Boolean(node.latest?.metrics.unraid);
}

export function nodeLamp(node: FleetNode, alerts: FleetAlert[] = []): LampState {
  if (!node.online) return "off";
  const mine = alerts.filter((alert) => alert.active && alert.node_id === node.node_id);
  if (mine.some((alert) => alert.severity === "critical")) return "stop";
  if (mine.length) return "caution";
  if (gamingUntil(node)) return "shunt";
  return "go";
}

export function isAndroid(node: FleetNode): boolean {
  return node.platform === "android";
}

export function lampText(state: LampState): string {
  return { go: "Online", caution: "Warnung", stop: "Kritisch", shunt: "Gaming Mode", off: "Offline" }[state];
}

export function platformLabel(node: FleetNode): string {
  if (isUnraid(node)) return "Unraid";
  const platform = node.platform.toLowerCase();
  if (platform.startsWith("win")) return "Windows";
  if (platform.startsWith("linux")) {
    const pretty = node.latest?.metrics.system?.platform ?? "";
    if (/cachyos/i.test(pretty)) return "CachyOS";
    if (/arch/i.test(pretty)) return "Arch Linux";
    if (/ubuntu/i.test(pretty)) return "Ubuntu";
    if (/fedora/i.test(pretty)) return "Fedora";
    return "Linux";
  }
  if (platform.startsWith("darwin")) return "macOS";
  if (platform === "android") return "Android";
  return node.platform;
}

export function cpuPercent(m?: Metrics | null): number | null {
  return num(m?.cpu?.percent);
}
export function memPercent(m?: Metrics | null): number | null {
  return num(m?.memory?.percent);
}
export function gpuPercent(m?: Metrics | null): number | null {
  return num(m?.gpus?.[0]?.percent);
}
export function cpuTemp(m?: Metrics | null): number | null {
  return num(m?.cpu?.temperature_c);
}
export function gpuTemp(m?: Metrics | null): number | null {
  return num(m?.lhm_gpus?.[0]?.temperature_c) ?? num(m?.gpus?.[0]?.temperature_c);
}
export function down(m?: Metrics | null): number | null {
  return num(m?.network?.download_mbps);
}
export function up(m?: Metrics | null): number | null {
  return num(m?.network?.upload_mbps);
}

export function level(value: number | null, caution = 75, stop = 90): "ok" | "caution" | "stop" {
  if (value == null) return "ok";
  if (value >= stop) return "stop";
  if (value >= caution) return "caution";
  return "ok";
}

export type Vendor = "amd" | "intel" | "nvidia";

export function vendorOf(name: string | null | undefined): Vendor | null {
  if (!name) return null;
  if (/nvidia|geforce|rtx|gtx|quadro/i.test(name)) return "nvidia";
  if (/amd|ryzen|radeon|threadripper|epyc/i.test(name)) return "amd";
  if (/intel|core\(tm\)|core i\d|xeon|arc a\d|celeron|pentium/i.test(name)) return "intel";
  return null;
}

export const VENDOR_NAME: Record<Vendor, string> = { amd: "AMD", intel: "Intel", nvidia: "NVIDIA" };

/**
 * A physical machine with one or more OS profiles (dual boot). Nodes without
 * a physical device form a machine of their own.
 */
export interface Machine {
  key: string;
  deviceId: string | null;
  name: string;
  profiles: FleetNode[];
  /** The profile that is online, or the one seen most recently. */
  active: FleetNode;
}

export function machinesOf(nodes: FleetNode[], devices: PhysicalDevice[] = []): Machine[] {
  const byDevice = new Map<string, FleetNode[]>();
  const machines: Machine[] = [];
  for (const node of nodes) {
    if (node.physical_device_id) {
      const list = byDevice.get(node.physical_device_id) ?? [];
      list.push(node);
      byDevice.set(node.physical_device_id, list);
    } else {
      machines.push({ key: node.node_id, deviceId: null, name: node.display_name, profiles: [node], active: node });
    }
  }
  for (const [deviceId, profiles] of byDevice) {
    const device = devices.find((item) => item.device_id === deviceId);
    profiles.sort((a, b) => a.display_name.localeCompare(b.display_name, "de"));
    const active = profiles.find((node) => node.online) ?? [...profiles].sort((a, b) => (b.last_seen_at ?? "").localeCompare(a.last_seen_at ?? ""))[0]!;
    machines.push({ key: deviceId, deviceId, name: device?.display_name ?? profiles[0]!.physical_device_name ?? active.display_name, profiles, active });
  }
  return machines;
}

/** The server's default groups have shouting placeholder names; show them in German. */
const DEFAULT_GROUPS: Record<string, string> = {
  "default-pcs-laptops": "PCs & Laptops",
  "default-servers": "Server",
  "default-mobile": "Mobil",
  "default-friends": "Freunde",
};

export function groupLabel(group: { group_id: string; name: string }): string {
  const fallback = DEFAULT_GROUPS[group.group_id];
  return fallback && group.name === group.name.toUpperCase() ? fallback : group.name;
}

export function sortByLayout(a: FleetNode, b: FleetNode): number {
  return a.fleet_position - b.fleet_position || a.display_name.localeCompare(b.display_name, "de");
}
