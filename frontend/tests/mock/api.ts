/*
 * In-memory mock of /api/v1 that follows the routers' permission checks
 * (require_commander_access, require_staff_access, manageable_node). Used by
 * Playwright routing and by the dev mock server for screenshots/Lighthouse.
 */
import type { DashboardRole, FleetNode, FleetTelemetryPoint, NetworkHistorySample } from "../../src/api/types.ts";
import { createFixtures, iso } from "./fixtures.ts";

export interface MockRequest { method: string; url: string; headers: Record<string, string>; body?: string | null }
export interface MockResponse { status: number; json?: unknown; body?: string; contentType?: string; headers?: Record<string, string> }

export const CREDENTIALS = {
  commander: { username: "bruno", password: "korrekt-pferd-batterie" },
  beta: { username: "kalle", password: "kalle-spielt-gern-mit" },
  friend: { username: "mia", password: "mia-fabriziert-factorio" },
  adminCode: "ABCD2345",
  betaCode: "BETA2345",
  invite: "K7QP-2MXD-9RTB",
};

interface Session { userId: string | null; username: string; role: DashboardRole }

export interface MockOptions { session?: DashboardRole | null; offline?: boolean }

export function createMockApi(options: MockOptions = {}) {
  const data = createFixtures();
  const sessions: Session[] = [];
  let session: Session | null = null;
  const log: Array<{ method: string; path: string; status: number }> = [];
  if (options.session) session = sessionFor(options.session);

  function sessionFor(role: DashboardRole): Session {
    const user = data.users.find((item) => item.role === role && item.active)!;
    return { userId: user.user_id, username: user.username, role };
  }

  const ok = (json: unknown, status = 200): MockResponse => ({ status, json });
  const fail = (status: number, detail: string): MockResponse => ({ status, json: { detail } });
  const empty = (): MockResponse => ({ status: 204 });

  function telemetry(nodeId: string, limit: number): FleetTelemetryPoint[] {
    const node = data.nodes.find((item) => item.node_id === nodeId);
    const base = node?.latest?.metrics;
    if (!base) return [];
    return Array.from({ length: limit }, (_, index) => {
      const t = limit - index;
      const wave = Math.sin(index / 6) * 12;
      return {
        point_id: `${nodeId}-p${index}`, sample_id: null, recorded_at: iso(-t * 5000),
        metrics: {
          ...base,
          cpu: { ...base.cpu, percent: Math.max(2, (base.cpu?.percent ?? 20) + wave), temperature_c: (base.cpu?.temperature_c ?? 50) + wave / 3 },
          memory: { ...base.memory, percent: (base.memory?.percent ?? 40) + wave / 5 },
          gpus: base.gpus?.map((gpu) => ({ ...gpu, percent: Math.max(0, (gpu.percent ?? 30) + wave * 1.5) })),
        },
      };
    });
  }

  function networkHistory(nodeId: string, limit: number): NetworkHistorySample[] {
    return Array.from({ length: limit }, (_, index) => ({
      recorded_at: iso(-(limit - index) * 30_000),
      network: { download_mbps: Math.abs(Math.sin(index / 4)) * 60 + (nodeId.length % 5), upload_mbps: Math.abs(Math.cos(index / 5)) * 9 },
    }));
  }

  function nodeOr404(nodeId: string): FleetNode | MockResponse {
    const node = data.nodes.find((item) => item.node_id === nodeId);
    if (!node || !visible(node)) return fail(404, "node not found");
    return node;
  }
  function visible(node: FleetNode): boolean {
    return session?.role !== "friend" || node.owner_user_id === session.userId;
  }
  function manageable(node: FleetNode): boolean {
    if (session?.role === "commander") return true;
    return session?.role === "friend" && node.owner_user_id === session.userId;
  }

  function handle(request: MockRequest): MockResponse {
    const url = new URL(request.url, "http://ncc.test");
    const path = url.pathname.replace(/^\/api\/v1/, "");
    const method = request.method.toUpperCase();
    const body = (() => { try { return request.body ? JSON.parse(request.body) : {}; } catch { return {}; } })();
    const result = route(method, path, url.searchParams, body, request);
    log.push({ method, path, status: result.status });
    return result;
  }

  function route(method: string, path: string, params: URLSearchParams, body: Record<string, any>, request: MockRequest): MockResponse {
    if (options.offline) return { status: 503, json: { detail: "unavailable" } };
    // Public
    if (path === "/version") return ok({ version: "0.6.2", api: "v1" });
    if (path === "/status/live") return ok({ status: "ok", service: "ncc-server", version: "0.6.2" });
    if (method === "POST" && path === "/admin-codes/redeem") {
      if (body.code === CREDENTIALS.adminCode) { session = { userId: null, username: "Commander", role: "commander" }; return ok({ status: "ok" }); }
      if (body.code === CREDENTIALS.betaCode) { session = { userId: null, username: "Beta Tester", role: "beta_tester" }; return ok({ status: "ok" }); }
      return fail(401, "invalid or expired admin code");
    }
    if (method === "POST" && path === "/users/login") {
      const match = Object.values(CREDENTIALS).find((item) => typeof item === "object" && item.username === body.username && item.password === body.password);
      if (!match || typeof match !== "object") return fail(401, "invalid username or password");
      const user = data.users.find((item) => item.username === match.username)!;
      session = { userId: user.user_id, username: user.username, role: user.role };
      return ok({ status: "ok" });
    }
    if (method === "POST" && path === "/users/register") {
      if (body.code !== CREDENTIALS.invite) return fail(403, "invite code is invalid or expired");
      if (data.users.some((user) => user.username === body.username)) return fail(409, "username already exists");
      const user = { user_id: `u-${body.username}`, username: body.username, role: "friend" as const, active: true, managed: true, created_at: iso(), full_statistics: false, device_count: 0 };
      data.users.push(user);
      session = { userId: user.user_id, username: user.username, role: "friend" };
      return ok(user, 201);
    }
    if (method === "POST" && path === "/admin-codes/logout") { session = null; return empty(); }

    // Everything else needs a session (or the legacy token)
    if (!session && request.headers["x-ncc-dashboard-token"] === "legacy-token") session = { userId: null, username: "Commander", role: "commander" };
    if (!session) return fail(401, "missing or invalid dashboard token");
    const role = session.role;
    const commander = role === "commander";
    const staff = role !== "friend";
    const needCommander = () => (commander ? null : fail(403, "commander access required"));
    const needStaff = () => (staff ? null : fail(403, "not available for friend accounts"));

    if (path === "/admin-codes/access") return ok({ access_role: role });
    if (path === "/users/me") return ok({ user_id: session.userId, username: session.username, role, active: true, managed: session.userId !== null, full_statistics: false, device_count: 0 });

    // Fleet
    if (path === "/fleet/summary") {
      const list = data.nodes.filter(visible);
      return ok({ total_nodes: list.length, online_nodes: list.filter((n) => n.online).length, offline_nodes: list.filter((n) => !n.online).length, pending_nodes: 1, telemetry_points: 184_220, server_time: iso() });
    }
    if (path === "/fleet/nodes" && method === "GET") return ok(data.nodes.filter(visible));
    if (path === "/fleet/groups" && method === "GET") return ok(data.groups);
    if (path === "/fleet/groups" && method === "POST") { const d = needCommander(); if (d) return d; const group = { group_id: `g-${data.groups.length}`, name: body.name, position: data.groups.length }; data.groups.push(group); return ok(group, 201); }
    if (path === "/fleet/layout" && method === "PUT") {
      const d = needCommander(); if (d) return d;
      for (const placement of body.placements ?? []) { const node = data.nodes.find((n) => n.node_id === placement.node_id); if (node) { node.fleet_group_id = placement.group_id; node.fleet_position = placement.position; } }
      return empty();
    }
    if (path === "/fleet/physical-devices" && method === "GET") return ok(data.physical);
    if (path === "/fleet/physical-devices" && method === "POST") {
      const d = needCommander(); if (d) return d;
      const device = { device_id: `d-${data.physical.length + 1}`, display_name: body.display_name, node_ids: body.node_ids };
      data.physical.push(device);
      for (const id of body.node_ids) { const node = data.nodes.find((n) => n.node_id === id); if (node) { node.physical_device_id = device.device_id; node.physical_device_name = device.display_name; } }
      return ok(device, 201);
    }
    let match = path.match(/^\/fleet\/physical-devices\/([^/]+)\/nodes\/([^/]+)$/);
    if (match) {
      const d = needCommander(); if (d) return d;
      const device = data.physical.find((item) => item.device_id === match![1]);
      const node = data.nodes.find((item) => item.node_id === match![2]);
      if (!device || !node) return fail(404, "physical device or node not found");
      if (method === "DELETE") { device.node_ids = device.node_ids.filter((id) => id !== node.node_id); node.physical_device_id = null; node.physical_device_name = null; return empty(); }
      device.node_ids.push(node.node_id); node.physical_device_id = device.device_id; node.physical_device_name = device.display_name; return ok(device);
    }
    if (path === "/fleet/alerts") return ok(data.alerts.filter((alert) => visible(data.nodes.find((n) => n.node_id === alert.node_id)!)));
    if (path === "/fleet/alerts/clear") { const d = needCommander(); if (d) return d; const count = data.alerts.filter((a) => a.active).length; data.alerts.forEach((a) => { if (a.active) { a.active = false; a.resolved_at = iso(); } }); return ok({ cleared: count }); }
    if (path === "/fleet/alert-policy" && method === "GET") return ok(data.policy);
    if (path === "/fleet/alert-policy" && method === "PUT") { const d = needCommander(); if (d) return d; Object.assign(data.policy, body); return ok(data.policy); }
    if (path === "/fleet/telegram" && method === "GET") { const d = needStaff(); if (d) return d; return ok(data.telegram); }
    if (path === "/fleet/telegram" && method === "PUT") { const d = needCommander(); if (d) return d; Object.assign(data.telegram, body); return ok(data.telegram); }
    if (path === "/fleet/telegram/test") { const d = needCommander(); if (d) return d; return ok({ sent: true }); }
    if (path === "/fleet/network/reset") { const d = needCommander(); if (d) return d; return empty(); }
    if (path === "/fleet/games" && method === "GET") return ok(data.games);
    if (path === "/fleet/games/stats") return ok({ ...data.stats, days: Number(params.get("days") ?? 30) });
    if (path === "/fleet/hardware/stats") return ok({ ...data.hardware, days: Number(params.get("days") ?? 30) });
    match = path.match(/^\/fleet\/games\/([^/]+)(\/artwork)?$/);
    if (match) {
      const game = data.games.find((item) => item.game_id === match![1]);
      if (!game) return fail(404, "game not found");
      if (match[2]) {
        if (method === "GET") return game.has_artwork ? { status: 200, body: artworkSvg(game.title), contentType: "image/svg+xml" } : fail(404, "artwork not found");
        const d = needCommander(); if (d) return d;
        if (method === "PUT") { game.has_artwork = true; game.artwork_source = "upload"; return ok(game); }
        if (method === "DELETE") { game.has_artwork = false; game.artwork_source = null; return ok(game); }
      }
      if (method === "PATCH") { const d = needCommander(); if (d) return d; game.steam_app_id = body.steam_app_id; game.manual_match = true; game.match_state = body.steam_app_id ? "matched" : "unmatched"; return ok(game); }
    }

    match = path.match(/^\/fleet\/nodes\/([^/]+)(\/.*)?$/);
    if (match) {
      const found = nodeOr404(decodeURIComponent(match[1]!));
      if (!("node_id" in found)) return found;
      const node = found;
      const sub = match[2] ?? "";
      if (sub === "" && method === "GET") return ok(node);
      if (sub === "/telemetry") return ok(telemetry(node.node_id, Math.min(Number(params.get("limit") ?? 120), 240)));
      if (sub === "/network/history") return ok(networkHistory(node.node_id, Number(params.get("limit") ?? 48)));
      if (sub === "/network/month") return ok({ period_start: new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString(), received_bytes: 412_000_000_000, sent_bytes: 38_200_000_000, samples: 12_000, available: node.online || node.node_id !== "n-lappi" });
      if (sub === "" && method === "DELETE") { const d = needCommander(); if (d) return d; data.nodes = data.nodes.filter((n) => n !== node); return empty(); }
      if (["/role", "/owner", "/release", "/update-channel"].includes(sub)) {
        const d = needCommander(); if (d) return d;
        if (sub === "/role") node.access_role = body.access_role;
        if (sub === "/owner") { node.owner_user_id = body.user_id; node.owner_name = data.users.find((u) => u.user_id === body.user_id)?.username ?? null; }
        if (sub === "/release") { node.pending_release_id = body.release_id; node.release_allow_downgrade = !!body.allow_downgrade; return empty(); }
        if (sub === "/update-channel") { node.update_channel = body.channel; return empty(); }
        return ok(node);
      }
      if (!manageable(node)) return fail(403, "commander access required");
      if (sub === "" && method === "PATCH") { node.display_name = body.display_name; return ok(node); }
      if (sub === "/gaming-mode") { node.gaming_mode_until = body.minutes ? iso(body.minutes * 60_000) : null; return ok(node); }
      if (sub === "/sensor-labels") { if (body.name || body.role) node.sensor_labels[body.key] = { name: body.name ?? null, role: body.role ?? null }; else delete node.sensor_labels[body.key]; return ok(node); }
      if (sub === "/update-check") { node.update_check_requested_at = iso(); return ok(node); }
      if (sub === "/game-settings") { node.game_tracking = body.game_tracking; node.auto_gaming_mode = body.auto_gaming_mode; return ok(node); }
    }

    // Chat
    if (path === "/fleet/chat/messages" && method === "GET") {
      const limit = Math.min(500, Number(params.get("limit") ?? 100));
      const after = params.get("after");
      const before = params.get("before");
      let list = data.chat;
      if (after) { const index = list.findIndex((m) => m.message_id === after); list = index >= 0 ? list.slice(index + 1) : []; return ok(list.slice(0, limit)); }
      if (before) { const index = list.findIndex((m) => m.message_id === before); list = index >= 0 ? list.slice(0, index) : []; }
      return ok(list.slice(-limit));
    }
    if (path === "/fleet/chat/messages" && method === "POST") {
      const message = { message_id: `m-${String(data.chat.length).padStart(3, "0")}`, sender_node_id: null, sender_user_id: session.userId, sender_name: session.username, body: body.body, body_format: body.body_format ?? "plain", attachment: null, created_at: iso() };
      data.chat.push(message as never);
      return ok(message, 201);
    }
    if (path === "/fleet/chat/uploads" && method === "POST") {
      const id = `m-${String(data.chat.length).padStart(3, "0")}`;
      const message = { message_id: id, sender_node_id: null, sender_user_id: session.userId, sender_name: session.username, body: "", body_format: "plain", attachment: { name: "upload.txt", content_type: "text/plain", size: 12, url: `/api/v1/fleet/chat/messages/${id}/attachment` }, created_at: iso() };
      data.chat.push(message as never);
      return ok(message, 201);
    }
    if (/^\/fleet\/chat\/messages\/[^/]+\/attachment$/.test(path)) return { status: 200, body: artworkSvg("Screenshot"), contentType: "image/svg+xml" };
    if (path === "/fleet/chat/participants") return ok([
      { user_id: "u-bruno", display_name: "bruno", role: "commander" },
      { user_id: "u-kalle", display_name: "kalle", role: "beta_tester" },
      { user_id: "u-mia", display_name: "mia", role: "friend" },
    ]);

    // Enrollment
    if (path === "/agent-pairings" && method === "GET") { const d = needStaff(); if (d) return d; return ok(data.pairings); }
    match = path.match(/^\/agent-pairings\/([^/]+)\/approve$/);
    if (match) {
      const pairing = data.pairings.find((item) => item.pairing_id === match![1]);
      if (!pairing || pairing.status === "claimed" || pairing.status === "cancelled") return fail(404, "pairing request not found");
      if (pairing.status === "expired") return fail(410, "pairing request expired");
      pairing.status = "approved";
      return ok(pairing);
    }
    if (path === "/agent-invitations" && method === "GET") { const d = needStaff(); if (d) return d; return ok(data.agentInvitations.filter((item) => item.status !== "revoked" || item.revoked_at)); }
    if (path === "/agent-invitations" && method === "POST") {
      const d = needCommander(); if (d) return d;
      const item = { token_id: `t${data.agentInvitations.length + 1}`, name: body.name, status: "ready" as const, node_id: null, node_name: null, created_at: iso(), expires_at: body.expires_hours ? iso(body.expires_hours * 3600_000) : null, last_used_at: null, revoked_at: null };
      data.agentInvitations.unshift(item);
      return ok({ ...item, token: "ncc_agent_9f8e7d6c5b4a3210fedcba9876543210" }, 201);
    }
    match = path.match(/^\/agent-invitations\/([^/]+)(\/revoke)?$/);
    if (match) {
      const d = needCommander(); if (d) return d;
      const item = data.agentInvitations.find((entry) => entry.token_id === match![1]);
      if (!item) return fail(404, "agent invitation not found");
      if (match[2]) { item.status = "revoked"; item.revoked_at = iso(); return ok(item); }
      if (!item.revoked_at) return fail(409, "revoke an invitation before removing it from the list");
      data.agentInvitations = data.agentInvitations.filter((entry) => entry !== item);
      return empty();
    }
    if (path === "/admin-codes" && method === "GET") { const d = needStaff(); if (d) return d; return ok(data.adminCodes); }
    if (path === "/admin-codes" && method === "POST") {
      const d = needCommander(); if (d) return d;
      const role = body.beta_tester ? "beta_tester" : "commander";
      data.adminCodes.unshift({ code_id: `c${data.adminCodes.length + 1}`, label: body.label, status: "ready", created_at: iso(), expires_at: iso(body.expires_minutes * 60_000), used_at: null, revoked_at: null, access_role: role });
      return ok({ code: "Q7W2KX9P", expires_at: iso(body.expires_minutes * 60_000), access_role: role }, 201);
    }
    match = path.match(/^\/admin-codes\/([^/]+)\/revoke$/);
    if (match) { const d = needCommander(); if (d) return d; const code = data.adminCodes.find((c) => c.code_id === match![1]); if (!code) return fail(404, "admin code not found"); code.status = "revoked"; code.revoked_at = iso(); return ok(code); }

    // Releases
    if (path === "/releases" && method === "GET") { const d = needStaff(); if (d) return d; return ok(data.releases); }
    if (path === "/releases/feed") { const d = needStaff(); if (d) return d; return ok({ enabled: true, repository: "DasBrunzel/ncc-cli", checked_at: iso(-20 * 60_000), error: null, registered: ["0.6.1"] }); }
    if (path === "/releases" && method === "POST") {
      const d = needCommander(); if (d) return d;
      const manifest = body.manifest ?? {};
      if (!manifest.payload_version) return fail(422, "manifest is missing payload_version");
      const release = { ...data.releases[0]!, release_id: `r-${data.releases.length + 1}`, payload_version: String(manifest.payload_version), channel: manifest.channel ?? "beta", released_at: iso(), assigned_nodes: 0 };
      data.releases.unshift(release);
      return ok(release, 201);
    }
    match = path.match(/^\/releases\/nodes\/([^/]+)(\/channel)?$/);
    if (match) {
      const d = needCommander(); if (d) return d;
      const node = data.nodes.find((n) => n.node_id === match![1]);
      if (!node) return fail(404, "node not found");
      if (match[2]) node.update_channel = body.channel; else { node.pending_release_id = body.release_id; node.release_allow_downgrade = !!body.allow_downgrade; }
      return empty();
    }

    // Users
    if (path === "/users/password") {
      if (!session.userId) return fail(403, "a personal account is required");
      return body.current_password === "falsch" ? fail(401, "current password is incorrect") : empty();
    }
    if (path === "/users/me/telegram" && method === "GET") return ok({ available: session.userId !== null, linked: false, telegram_name: null, weekly_recap: true, bot_username: "no0bz_ncc_bot" });
    if (path === "/users/me/telegram/link") return ok({ code: "TG-4821", expires_at: iso(10 * 60_000), deep_link: "https://t.me/no0bz_ncc_bot?start=TG-4821" });
    if (path === "/users/me/telegram" && method === "PATCH") return fail(404, "no Telegram chat linked");
    if (path === "/users/me/telegram" && method === "DELETE") return empty();
    if (path === "/users" && method === "GET") { const d = needCommander(); if (d) return d; return ok(data.users); }
    if (path === "/users" && method === "POST") { const d = needCommander(); if (d) return d; const user = { user_id: `u-${body.username}`, username: body.username, role: body.role, active: true, managed: true, created_at: iso(), full_statistics: false, device_count: 0 }; data.users.push(user); return ok(user, 201); }
    if (path === "/users/invites" && method === "GET") { const d = needCommander(); if (d) return d; return ok(data.invites); }
    if (path === "/users/invites" && method === "POST") { const d = needCommander(); if (d) return d; const invite = { invite_id: `i${data.invites.length + 1}`, label: body.label, created_at: iso(), expires_at: iso(body.expires_days * 86400_000), status: "open" as const, used_by: null }; data.invites.unshift(invite); return ok({ ...invite, code: "WX3R-8KDP-2QZN" }, 201); }
    match = path.match(/^\/users\/invites\/([^/]+)\/revoke$/);
    if (match) { const d = needCommander(); if (d) return d; const invite = data.invites.find((i) => i.invite_id === match![1]); if (!invite) return fail(404, "invite not found"); invite.status = "revoked"; return ok(invite); }
    match = path.match(/^\/users\/([^/]+)$/);
    if (match && method === "PATCH") { const d = needCommander(); if (d) return d; const user = data.users.find((u) => u.user_id === match![1]); if (!user) return fail(404, "user not found"); Object.assign(user, Object.fromEntries(Object.entries(body).filter(([, v]) => v !== undefined))); return ok(user); }

    return fail(404, `mock: no route for ${method} ${path}`);
  }

  return {
    handle,
    data,
    log,
    get session() { return session; },
    expireSession() { if (session) sessions.push(session); session = null; },
    setOffline(value: boolean) { options.offline = value; },
  };
}

function artworkSvg(title: string): string {
  const hue = [...title].reduce((sum, char) => sum + char.charCodeAt(0), 0) % 360;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 920 430"><rect width="920" height="430" fill="hsl(${hue} 45% 32%)"/><path d="M0 330 L920 210 L920 430 L0 430Z" fill="hsl(${hue} 45% 22%)"/><text x="48" y="380" font-family="sans-serif" font-size="64" font-weight="700" fill="white">${title.replace(/[<&>]/g, "")}</text></svg>`;
}

export type MockApi = ReturnType<typeof createMockApi>;
