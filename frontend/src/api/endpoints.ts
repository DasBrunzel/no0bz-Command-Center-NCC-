import { request } from "./client";
import type {
  AccessRole, AccountInvite, ArtworkCandidate, AccountInviteCreated, AdminCode, AdminCodeCreated, AgentInvitation,
  AgentInvitationCreated, AgentPairing, AgentRelease, AlertPolicy, ChatMessage, ChatParticipant,
  DashboardAccess, DashboardRole, DashboardUser, FleetAlert, FleetGroup, FleetLayoutPlacement, FleetNetwork, FleetNode,
  FleetSummary, FleetTelemetryPoint, Game, GameTracking, HardwareStats, NetworkHistorySample,
  NetworkUsageSummary, PhysicalDevice, PlaytimeStats, ReleaseFeedStatus, SensorRole, ServerVersion,
  TelegramAccount, TelegramLinkCode, TelegramSettings, TelegramSettingsUpdate, UpdateChannel,
} from "./types";

const id = encodeURIComponent;
const offset = () => -new Date().getTimezoneOffset();

function query(params: Record<string, string | number | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) if (value !== null && value !== undefined && value !== "") search.set(key, String(value));
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const api = {
  version: () => request<ServerVersion>("/version"),
  live: () => request<{ status: string; version: string }>("/status/live"),

  auth: {
    redeemCode: (code: string) => request<{ status: string }>("/admin-codes/redeem", { method: "POST", json: { code }, authRequest: true }),
    login: (username: string, password: string) => request<{ status: string }>("/users/login", { method: "POST", json: { username, password }, authRequest: true }),
    register: (code: string, username: string, password: string) =>
      request<DashboardUser>("/users/register", { method: "POST", json: { code, username, password }, authRequest: true }),
    logout: () => request<void>("/admin-codes/logout", { method: "POST", authRequest: true }),
    access: () => request<DashboardAccess>("/admin-codes/access"),
    me: () => request<DashboardUser>("/users/me"),
    changePassword: (current_password: string, new_password: string) =>
      request<void>("/users/password", { method: "POST", json: { current_password, new_password } }),
  },

  fleet: {
    summary: () => request<FleetSummary>("/fleet/summary"),
    nodes: () => request<FleetNode[]>("/fleet/nodes"),
    node: (nodeId: string) => request<FleetNode>(`/fleet/nodes/${id(nodeId)}`),
    groups: () => request<FleetGroup[]>("/fleet/groups"),
    createGroup: (name: string) => request<FleetGroup>("/fleet/groups", { method: "POST", json: { name } }),
    renameGroup: (groupId: string, name: string) => request<FleetGroup>(`/fleet/groups/${id(groupId)}`, { method: "PATCH", json: { name } }),
    network: (minutes = 30) => request<FleetNetwork>(`/fleet/network${query({ minutes })}`),
    saveLayout: (placements: FleetLayoutPlacement[]) => request<void>("/fleet/layout", { method: "PUT", json: { placements } }),
    physicalDevices: () => request<PhysicalDevice[]>("/fleet/physical-devices"),
    createPhysicalDevice: (display_name: string, node_ids: string[]) =>
      request<PhysicalDevice>("/fleet/physical-devices", { method: "POST", json: { display_name, node_ids } }),
    attachProfile: (deviceId: string, nodeId: string) =>
      request<PhysicalDevice>(`/fleet/physical-devices/${id(deviceId)}/nodes/${id(nodeId)}`, { method: "POST" }),
    detachProfile: (deviceId: string, nodeId: string) =>
      request<void>(`/fleet/physical-devices/${id(deviceId)}/nodes/${id(nodeId)}`, { method: "DELETE" }),
    alerts: (limit = 100) => request<FleetAlert[]>(`/fleet/alerts${query({ limit })}`),
    clearAlerts: () => request<{ cleared: number }>("/fleet/alerts/clear", { method: "POST" }),
    alertPolicy: () => request<AlertPolicy>("/fleet/alert-policy"),
    saveAlertPolicy: (policy: AlertPolicy) => request<AlertPolicy>("/fleet/alert-policy", { method: "PUT", json: policy }),
    telegram: () => request<TelegramSettings>("/fleet/telegram"),
    saveTelegram: (settings: TelegramSettingsUpdate) => request<TelegramSettings>("/fleet/telegram", { method: "PUT", json: settings }),
    testTelegram: () => request<{ sent: boolean }>("/fleet/telegram/test", { method: "POST" }),
    rename: (nodeId: string, display_name: string) => request<FleetNode>(`/fleet/nodes/${id(nodeId)}`, { method: "PATCH", json: { display_name } }),
    forget: (nodeId: string) => request<void>(`/fleet/nodes/${id(nodeId)}`, { method: "DELETE" }),
    setRole: (nodeId: string, access_role: AccessRole) => request<FleetNode>(`/fleet/nodes/${id(nodeId)}/role`, { method: "PATCH", json: { access_role } }),
    setOwner: (nodeId: string, user_id: string | null) => request<FleetNode>(`/fleet/nodes/${id(nodeId)}/owner`, { method: "PUT", json: { user_id } }),
    setGamingMode: (nodeId: string, minutes: number) => request<FleetNode>(`/fleet/nodes/${id(nodeId)}/gaming-mode`, { method: "PUT", json: { minutes } }),
    setSensorLabel: (nodeId: string, key: string, name: string | null, role: SensorRole | null) =>
      request<FleetNode>(`/fleet/nodes/${id(nodeId)}/sensor-labels`, { method: "PUT", json: { key, name, role } }),
    requestUpdateCheck: (nodeId: string) => request<FleetNode>(`/fleet/nodes/${id(nodeId)}/update-check`, { method: "POST" }),
    assignRelease: (nodeId: string, release_id: string | null, allow_downgrade = false) =>
      request<void>(`/fleet/nodes/${id(nodeId)}/release`, { method: "PUT", json: { release_id, allow_downgrade } }),
    setUpdateChannel: (nodeId: string, channel: UpdateChannel) =>
      request<void>(`/fleet/nodes/${id(nodeId)}/update-channel`, { method: "PUT", json: { channel } }),
    telemetry: (nodeId: string, limit = 120, after?: string) =>
      request<FleetTelemetryPoint[]>(`/fleet/nodes/${id(nodeId)}/telemetry${query({ limit, after })}`),
    networkHistory: (nodeId: string, limit = 48) => request<NetworkHistorySample[]>(`/fleet/nodes/${id(nodeId)}/network/history${query({ limit })}`),
    networkMonth: (nodeId: string) => request<NetworkUsageSummary>(`/fleet/nodes/${id(nodeId)}/network/month`),
    resetNetwork: () => request<void>("/fleet/network/reset", { method: "POST" }),
    hardwareStats: (days: number, nodeId?: string | null) =>
      request<HardwareStats>(`/fleet/hardware/stats${query({ days, node_id: nodeId, utc_offset_minutes: offset() })}`),
  },

  games: {
    list: () => request<Game[]>("/fleet/games"),
    stats: (days: number, nodeId?: string | null) =>
      request<PlaytimeStats>(`/fleet/games/stats${query({ days, node_id: nodeId, utc_offset_minutes: offset() })}`),
    update: (gameId: string, steam_app_id: number | null) => request<Game>(`/fleet/games/${id(gameId)}`, { method: "PATCH", json: { steam_app_id } }),
    artworkUrl: (gameId: string) => `/api/v1/fleet/games/${id(gameId)}/artwork`,
    artwork: (gameId: string, signal?: AbortSignal) => request<Response>(`/fleet/games/${id(gameId)}/artwork`, { raw: true, signal }),
    uploadArtwork: (gameId: string, image: Blob) =>
      request<Game>(`/fleet/games/${id(gameId)}/artwork`, { method: "PUT", body: image, headers: { "Content-Type": image.type || "image/jpeg" } }),
    removeArtwork: (gameId: string) => request<Game>(`/fleet/games/${id(gameId)}/artwork`, { method: "DELETE" }),
    searchArtwork: (gameId: string, query?: string) =>
      request<ArtworkCandidate[]>(`/fleet/games/${id(gameId)}/artwork/candidates${query ? `?query=${encodeURIComponent(query)}` : ""}`),
    chooseArtwork: (gameId: string, index: number) => request<Game>(`/fleet/games/${id(gameId)}/artwork/candidates/${index}`, { method: "POST" }),
    setNodeSettings: (nodeId: string, game_tracking: GameTracking, auto_gaming_mode: boolean) =>
      request<FleetNode>(`/fleet/nodes/${id(nodeId)}/game-settings`, { method: "PUT", json: { game_tracking, auto_gaming_mode } }),
  },

  chat: {
    messages: (params: { limit?: number; before?: string; after?: string } = {}) =>
      request<ChatMessage[]>(`/fleet/chat/messages${query({ limit: params.limit ?? 50, before: params.before, after: params.after })}`),
    participants: () => request<ChatParticipant[]>("/fleet/chat/participants"),
    send: (body: string, body_format: "plain" | "markdown") => request<ChatMessage>("/fleet/chat/messages", { method: "POST", json: { body, body_format } }),
    upload: (file: File, body: string, body_format: "plain" | "markdown") => {
      const form = new FormData();
      form.set("file", file);
      form.set("body", body);
      form.set("body_format", body_format);
      return request<ChatMessage>("/fleet/chat/uploads", { method: "POST", body: form });
    },
    attachment: (messageId: string, signal?: AbortSignal) => request<Response>(`/fleet/chat/messages/${id(messageId)}/attachment`, { raw: true, signal }),
  },

  pairings: {
    list: () => request<AgentPairing[]>("/agent-pairings"),
    approve: (pairingId: string) => request<AgentPairing>(`/agent-pairings/${id(pairingId)}/approve`, { method: "POST" }),
    cancel: (pairingId: string) => request<AgentPairing>(`/agent-pairings/${id(pairingId)}/cancel`, { method: "POST" }),
  },

  invitations: {
    list: () => request<AgentInvitation[]>("/agent-invitations"),
    create: (name: string, expires_hours: number, access_role: AccessRole = "commander") =>
      request<AgentInvitationCreated>("/agent-invitations", { method: "POST", json: { name, expires_hours, access_role } }),
    revoke: (tokenId: string) => request<AgentInvitation>(`/agent-invitations/${id(tokenId)}/revoke`, { method: "POST" }),
    remove: (tokenId: string) => request<void>(`/agent-invitations/${id(tokenId)}`, { method: "DELETE" }),
  },

  adminCodes: {
    list: () => request<AdminCode[]>("/admin-codes"),
    create: (label: string, expires_minutes: number, beta_tester: boolean) =>
      request<AdminCodeCreated>("/admin-codes", { method: "POST", json: { label, expires_minutes, beta_tester } }),
    revoke: (codeId: string) => request<AdminCode>(`/admin-codes/${id(codeId)}/revoke`, { method: "POST" }),
  },

  releases: {
    list: () => request<AgentRelease[]>("/releases"),
    feed: () => request<ReleaseFeedStatus>("/releases/feed"),
    create: (manifest: Record<string, unknown>) => request<AgentRelease>("/releases", { method: "POST", json: { manifest } }),
    assign: (nodeId: string, release_id: string | null, allow_downgrade = false) =>
      request<void>(`/releases/nodes/${id(nodeId)}`, { method: "PUT", json: { release_id, allow_downgrade } }),
    setChannel: (nodeId: string, channel: UpdateChannel) => request<void>(`/releases/nodes/${id(nodeId)}/channel`, { method: "PUT", json: { channel } }),
  },

  users: {
    list: () => request<DashboardUser[]>("/users"),
    create: (username: string, password: string, role: DashboardRole) => request<DashboardUser>("/users", { method: "POST", json: { username, password, role } }),
    update: (userId: string, patch: { role?: DashboardRole; active?: boolean; full_statistics?: boolean }) =>
      request<DashboardUser>(`/users/${id(userId)}`, { method: "PATCH", json: patch }),
    remove: (userId: string) => request<void>(`/users/${id(userId)}`, { method: "DELETE" }),
    invites: () => request<AccountInvite[]>("/users/invites"),
    createInvite: (label: string, expires_days: number) => request<AccountInviteCreated>("/users/invites", { method: "POST", json: { label, expires_days } }),
    revokeInvite: (inviteId: string) => request<AccountInvite>(`/users/invites/${id(inviteId)}/revoke`, { method: "POST" }),
    telegram: () => request<TelegramAccount>("/users/me/telegram"),
    telegramLink: () => request<TelegramLinkCode>("/users/me/telegram/link", { method: "POST" }),
    updateTelegram: (weekly_recap: boolean) => request<TelegramAccount>("/users/me/telegram", { method: "PATCH", json: { weekly_recap } }),
    unlinkTelegram: () => request<void>("/users/me/telegram", { method: "DELETE" }),
  },
};

/** Query keys; one place so mutations invalidate the right things. */
export const qk = {
  version: ["version"] as const,
  session: ["session"] as const,
  summary: ["fleet", "summary"] as const,
  nodes: ["fleet", "nodes"] as const,
  node: (nodeId: string) => ["fleet", "node", nodeId] as const,
  groups: ["fleet", "groups"] as const,
  physical: ["fleet", "physical"] as const,
  alerts: ["fleet", "alerts"] as const,
  alertPolicy: ["fleet", "alert-policy"] as const,
  telegram: ["fleet", "telegram"] as const,
  telemetry: (nodeId: string) => ["fleet", "telemetry", nodeId] as const,
  networkHistory: (nodeId: string) => ["fleet", "network-history", nodeId] as const,
  networkMonth: (nodeId: string) => ["fleet", "network-month", nodeId] as const,
  fleetNetwork: (minutes: number) => ["fleet", "network", minutes] as const,
  hardwareStats: (days: number, nodeId: string | null) => ["fleet", "hardware-stats", days, nodeId] as const,
  games: ["games"] as const,
  gameStats: (days: number, nodeId: string | null) => ["games", "stats", days, nodeId] as const,
  chat: ["chat", "messages"] as const,
  participants: ["chat", "participants"] as const,
  pairings: ["pairings"] as const,
  invitations: ["invitations"] as const,
  adminCodes: ["admin-codes"] as const,
  releases: ["releases"] as const,
  releaseFeed: ["releases", "feed"] as const,
  users: ["users"] as const,
  invites: ["users", "invites"] as const,
  myTelegram: ["users", "me", "telegram"] as const,
};

/** Polling intervals in ms (see the brief's table). */
export const POLL = {
  chat: 5_000,
  pairings: 5_000,
  nodes: 4_000,
  fleetNetwork: 5_000,
  alerts: 5_000,
  summary: 10_000,
  networkHistory: 30_000,
  games: 60_000,
  hardwareStats: 120_000,
  networkMonth: 300_000,
  telemetry: 10_000,
  admin: 30_000,
} as const;
