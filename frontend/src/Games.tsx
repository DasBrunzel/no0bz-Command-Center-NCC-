import React, { useEffect, useMemo, useState } from "react";
import { Gamepad2, Trophy } from "lucide-react";
import { Meter as ConceptMeter, SectionHead as ConceptSectionHead } from "./concept/components";

export type NowPlaying = {
  session_id: string;
  game_id: string | null;
  title: string | null;
  launcher: string | null;
  started_at: string;
  has_artwork: boolean;
  genres: string[];
};
export type GameTracking = "off" | "presence" | "titles";
type GameNode = {
  node_id: string;
  display_name: string;
  platform: string;
  online: boolean;
  metadata: Record<string, unknown>;
  gaming_mode_until: string | null;
  auto_gaming_until?: string | null;
  auto_gaming_mode?: boolean;
  game_tracking?: GameTracking;
  now_playing?: NowPlaying | null;
  latest: { metrics: Record<string, any> } | null;
};
type HardwareValue = { average: number; max: number };
type GameEntry = {
  game_id: string | null;
  title: string | null;
  launcher: string | null;
  has_artwork: boolean;
  genres: string[];
  seconds: number;
  sessions: number;
  last_played_at: string;
  hardware: Record<string, HardwareValue>;
  energy_wh?: number;
};
type PlaytimeStats = {
  days: number;
  total_seconds: number;
  session_count: number;
  game_count: number;
  longest_session: { title: string | null; node_name: string | null; seconds: number; started_at: string } | null;
  games: GameEntry[];
  nodes: { node_id: string; display_name: string; seconds: number }[];
  daily: { date: string; seconds: number }[];
  heatmap: number[][];
  recent_sessions: { session_id: string; game_id: string | null; title: string | null; node_name: string; started_at: string; ended_at: string; seconds: number }[];
};

const LAUNCHERS: Record<string, string> = { steam: "Steam", epic: "Epic Games", gog: "GOG", xbox: "Xbox-App", other: "Andere" };
const WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
const PERIODS = [{ days: 7, label: "7 Tage" }, { days: 30, label: "30 Tage" }, { days: 365, label: "1 Jahr" }, { days: 0, label: "Gesamt" }];
const authHeaders = (token: string): Record<string, string> => (token ? { "X-NCC-Dashboard-Token": token } : {});

export const playtime = (seconds: number) => {
  if (seconds < 60) return seconds > 0 ? "< 1 Min." : "0 Min.";
  const hours = Math.floor(seconds / 3600), minutes = Math.floor((seconds % 3600) / 60);
  return hours ? `${hours} Std. ${String(minutes).padStart(2, "0")} Min.` : `${minutes} Min.`;
};
// Summary tiles have room for one short value only.
const playtimeShort = (seconds: number) => seconds >= 3600
  ? <>{(seconds / 3600).toLocaleString("de-DE", { maximumFractionDigits: 1 })}<small>Std.</small></>
  : <>{Math.round(seconds / 60)}<small>Min.</small></>;
const since = (value: string) => playtime(Math.max(0, (Date.now() - new Date(value).getTime()) / 1000));
const gameName = (title: string | null) => title || "Ein Spiel";

/** Return the later of manual and automatic gaming mode while it is active. */
export function activeGamingUntil(node: Pick<GameNode, "gaming_mode_until" | "auto_gaming_until">): string | null {
  const now = Date.now();
  const active = [node.gaming_mode_until, node.auto_gaming_until].filter((value): value is string => !!value && new Date(value).getTime() > now);
  return active.sort((left, right) => new Date(right).getTime() - new Date(left).getTime())[0] ?? null;
}
const autoOnly = (node: GameNode) => {
  const manual = !!node.gaming_mode_until && new Date(node.gaming_mode_until).getTime() > Date.now();
  return !manual && !!node.auto_gaming_until && new Date(node.auto_gaming_until).getTime() > Date.now();
};

// Artwork needs the dashboard token, so it is fetched once per game and kept
// as an object URL for the lifetime of the page.
const artworkCache = new Map<string, Promise<string | null>>();
function useArtwork(gameId: string | null, hasArtwork: boolean, token: string) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!gameId || !hasArtwork) { setUrl(null); return; }
    let current = true;
    let pending = artworkCache.get(gameId);
    if (!pending) {
      pending = fetch(`/api/v1/fleet/games/${gameId}/artwork`, { headers: authHeaders(token) })
        .then((response) => (response.ok ? response.blob() : null))
        .then((blob) => (blob ? URL.createObjectURL(blob) : null))
        .catch(() => null);
      artworkCache.set(gameId, pending);
    }
    void pending.then((value) => { if (current) setUrl(value); });
    return () => { current = false; };
  }, [gameId, hasArtwork, token]);
  return url;
}

function GameArt({ gameId, title, hasArtwork, token, size = "large" }: { gameId: string | null; title: string | null; hasArtwork: boolean; token: string; size?: "large" | "small" }) {
  const url = useArtwork(gameId, hasArtwork, token);
  return <div className={`game-art ${size}`}>
    {url ? <img src={url} alt="" /> : <span aria-hidden="true">{title ? title.trim().charAt(0).toUpperCase() : <Gamepad2 size={size === "large" ? 34 : 16} />}</span>}
  </div>;
}

export function NowPlayingCard({ node, token, canManage }: { node: GameNode; token: string; canManage: boolean }) {
  const [saving, setSaving] = useState(false);
  const playing = node.now_playing;
  const isWindows = node.platform === "windows" && node.metadata.source !== "unraid-api";
  if (!isWindows || (!playing && !canManage)) return null;
  const metrics = node.latest?.metrics || {};
  const gpu = metrics.lhm_gpus?.[0]?.temperature_c ?? metrics.gpus?.[0]?.temperature_c;
  const cpu = metrics.cpu?.temperature_c;
  const save = async (gameTracking: GameTracking, autoGaming: boolean) => {
    setSaving(true);
    const response = await fetch(`/api/v1/fleet/nodes/${node.node_id}/game-settings`, {
      method: "PUT",
      headers: { ...authHeaders(token), "Content-Type": "application/json" },
      body: JSON.stringify({ game_tracking: gameTracking, auto_gaming_mode: autoGaming }),
    });
    if (response.ok) { window.location.reload(); return; }
    setSaving(false);
    window.alert("Die Einstellung zur Spielerkennung konnte nicht gespeichert werden.");
  };
  const tracking = node.game_tracking || "titles", autoGaming = node.auto_gaming_mode ?? true;
  return <div className={`detail-card game-now-card ${playing ? "playing" : ""}`}>
    {playing ? <div className="game-now">
      <GameArt gameId={playing.game_id} title={playing.title} hasArtwork={playing.has_artwork} token={token} />
      <div className="game-now-info">
        <span className="game-now-label"><span className="pulse-dot" /> Spielt gerade</span>
        <h2>{gameName(playing.title)}</h2>
        <p>{playing.launcher ? `${LAUNCHERS[playing.launcher] || playing.launcher} · ` : ""}seit {since(playing.started_at)}</p>
        {playing.genres.length > 0 && <div className="game-genres">{playing.genres.slice(0, 4).map((genre) => <span key={genre}>{genre}</span>)}</div>}
        <div className="game-now-sensors">
          <span>CPU <b>{typeof cpu === "number" ? `${cpu.toFixed(0)} °C` : "—"}</b></span>
          <span>GPU <b>{typeof gpu === "number" ? `${gpu.toFixed(0)} °C` : "—"}</b></span>
          {autoOnly(node) && <span className="game-auto">Gaming Mode automatisch aktiv</span>}
        </div>
      </div>
    </div> : <ConceptSectionHead title="Spielerkennung" aside={<span className="muted-small">Kein Spiel aktiv</span>} />}
    {canManage && <div className="game-settings">
      <label>Spielerkennung
        <select value={tracking} disabled={saving} onChange={(event) => void save(event.target.value as GameTracking, autoGaming)}>
          <option value="titles">Mit Spieltitel</option>
          <option value="presence">Nur „spielt gerade“</option>
          <option value="off">Aus</option>
        </select>
      </label>
      <label className="game-toggle"><input type="checkbox" checked={autoGaming} disabled={saving || tracking === "off"} onChange={(event) => void save(tracking, event.target.checked)} /> Gaming Mode automatisch einschalten</label>
    </div>}
  </div>;
}

export function NowPlayingStrip({ nodes, token, onOpen }: { nodes: GameNode[]; token: string; onOpen: (nodeId: string) => void }) {
  const playing = nodes.filter((node) => node.online && node.now_playing);
  if (!playing.length) return null;
  return <div className="now-playing-strip">
    {playing.map((node) => {
      const game = node.now_playing as NowPlaying;
      return <button type="button" key={node.node_id} onClick={() => onOpen(node.node_id)}>
        <GameArt gameId={game.game_id} title={game.title} hasArtwork={game.has_artwork} token={token} size="small" />
        <span><small>{node.display_name} spielt gerade</small><b>{gameName(game.title)}</b></span>
        <em>{since(game.started_at)}</em>
      </button>;
    })}
  </div>;
}

function DailyChart({ stats }: { stats: PlaytimeStats }) {
  const [hovered, setHovered] = useState<number | null>(null);
  const bars = useMemo(() => {
    const byDate = new Map(stats.daily.map((entry) => [entry.date, entry.seconds]));
    const today = new Date();
    const key = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
    if (stats.days && stats.days <= 31) {
      return Array.from({ length: stats.days }, (_, index) => {
        const date = new Date(today.getFullYear(), today.getMonth(), today.getDate() - (stats.days - 1 - index));
        return { label: date.toLocaleDateString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit" }), short: String(date.getDate()), seconds: byDate.get(key(date)) || 0 };
      });
    }
    // Longer ranges are summed per month so a bar stays readable.
    const months = new Map<string, number>();
    for (const entry of stats.daily) months.set(entry.date.slice(0, 7), (months.get(entry.date.slice(0, 7)) || 0) + entry.seconds);
    const first = stats.days ? new Date(today.getFullYear(), today.getMonth() - 11, 1) : stats.daily.length ? new Date(`${stats.daily[0].date.slice(0, 7)}-01T00:00:00`) : today;
    const result = [];
    for (let cursor = new Date(first.getFullYear(), first.getMonth(), 1); cursor <= today; cursor = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1)) {
      const monthKey = `${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, "0")}`;
      result.push({ label: cursor.toLocaleDateString("de-DE", { month: "long", year: "numeric" }), short: cursor.toLocaleDateString("de-DE", { month: "short" }), seconds: months.get(monthKey) || 0 });
    }
    return result;
  }, [stats]);
  const max = Math.max(...bars.map((bar) => bar.seconds), 1);
  const focus = hovered !== null ? bars[hovered] : null;
  const labelEvery = Math.ceil(bars.length / 10);
  return <div className="playtime-chart">
    <div className="playtime-chart-focus">{focus ? <><span>{focus.label}</span><b>{playtime(focus.seconds)}</b></> : <span>Zeige auf einen Balken für Details</span>}</div>
    <div className="playtime-bars" onMouseLeave={() => setHovered(null)}>
      {bars.map((bar, index) => <div key={bar.label} className={`playtime-bar ${hovered === index ? "hovered" : ""}`} onMouseEnter={() => setHovered(index)} title={`${bar.label}: ${playtime(bar.seconds)}`}>
        <span style={{ height: `${bar.seconds ? Math.max(2, (bar.seconds / max) * 100) : 0}%` }} />
      </div>)}
    </div>
    <div className="playtime-axis">{bars.map((bar, index) => <span key={bar.label}>{index % labelEvery === 0 ? bar.short : ""}</span>)}</div>
  </div>;
}

function Heatmap({ heatmap }: { heatmap: number[][] }) {
  const [hovered, setHovered] = useState<string | null>(null);
  const max = Math.max(...heatmap.flat(), 1);
  return <div className="playtime-heatmap">
    <div className="playtime-chart-focus">{hovered || <span>Wann wird gespielt?</span>}</div>
    <div className="heatmap-grid" onMouseLeave={() => setHovered(null)}>
      <span />
      {Array.from({ length: 24 }, (_, hour) => <span key={hour} className="heatmap-hour">{hour % 3 === 0 ? hour : ""}</span>)}
      {heatmap.map((row, day) => <React.Fragment key={day}>
        <span className="heatmap-day">{WEEKDAYS[day]}</span>
        {row.map((seconds, hour) => {
          const text = `${WEEKDAYS[day]} ${String(hour).padStart(2, "0")}–${String(hour + 1).padStart(2, "0")} Uhr: ${playtime(seconds)}`;
          return <i key={hour} title={text} onMouseEnter={() => setHovered(text)} style={{ opacity: seconds ? 0.18 + (seconds / max) * 0.82 : 1 }} className={seconds ? "filled" : ""} />;
        })}
      </React.Fragment>)}
    </div>
  </div>;
}

export function PlaytimeStatistics({ nodes, token, canManage }: { nodes: GameNode[]; token: string; canManage: boolean }) {
  const [days, setDays] = useState(30);
  const [nodeId, setNodeId] = useState("");
  const [stats, setStats] = useState<PlaytimeStats | null>(null);
  const [failed, setFailed] = useState(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let current = true;
    const load = async () => {
      const params = new URLSearchParams({ days: String(days), utc_offset_minutes: String(-new Date().getTimezoneOffset()) });
      if (nodeId) params.set("node_id", nodeId);
      try {
        const response = await fetch(`/api/v1/fleet/games/stats?${params}`, { headers: authHeaders(token) });
        if (!response.ok) throw new Error("REQUEST");
        const value = await response.json() as PlaytimeStats;
        if (current) { setStats(value); setFailed(false); }
      } catch { if (current) setFailed(true); }
    };
    void load();
    const timer = window.setInterval(() => { if (document.visibilityState === "visible") void load(); }, 60_000);
    return () => { current = false; window.clearInterval(timer); };
  }, [days, nodeId, token, revision]);

  const correct = async (game: GameEntry) => {
    if (!game.game_id) return;
    const answer = window.prompt(`Steam-Shop-Link oder App-ID für „${game.title}“ eingeben.\nLeer lassen, wenn das Spiel nicht bei Steam erhältlich ist.`, "");
    if (answer === null) return;
    const match = answer.match(/\/app\/(\d+)/) || answer.trim().match(/^(\d+)$/);
    if (answer.trim() && !match) { window.alert("Bitte einen Link wie https://store.steampowered.com/app/1091500/ oder nur die Zahl eingeben."); return; }
    const response = await fetch(`/api/v1/fleet/games/${game.game_id}`, {
      method: "PATCH",
      headers: { ...authHeaders(token), "Content-Type": "application/json" },
      body: JSON.stringify({ steam_app_id: match ? Number(match[1]) : null }),
    });
    if (!response.ok) { window.alert("Die Zuordnung konnte nicht gespeichert werden."); return; }
    artworkCache.delete(game.game_id);
    window.alert(match ? "Gespeichert. Cover und Infos werden in etwa einer Minute geladen." : "Gespeichert. Das Spiel wird ohne Steam-Infos angezeigt.");
    setRevision((value) => value + 1);
  };

  const windowsNodes = nodes.filter((node) => node.platform === "windows" && node.metadata.source !== "unraid-api");
  const top = stats?.games[0];
  const topSeconds = Math.max(top?.seconds || 0, 1);
  const hardwareGames = (stats?.games || []).filter((game) => game.title && Object.keys(game.hardware).length);
  const hw = (game: GameEntry, name: string, unit: string) => {
    const value = game.hardware[name];
    return value ? <>{value.average.toFixed(0)}{unit} <small>max {value.max.toFixed(0)}{unit}</small></> : "—";
  };
  return <>
    <div className="filter-bar playtime-filters">
      <div className="segmented">{PERIODS.map((period) => <button type="button" key={period.days} className={days === period.days ? "selected" : ""} onClick={() => setDays(period.days)}>{period.label}</button>)}</div>
      <select value={nodeId} onChange={(event) => setNodeId(event.target.value)} aria-label="Gerät">
        <option value="">Alle Geräte</option>
        {windowsNodes.map((node) => <option key={node.node_id} value={node.node_id}>{node.display_name}</option>)}
      </select>
    </div>
    {failed && !stats && <div className="detail-card empty">Die Spielzeit-Statistik konnte nicht geladen werden.</div>}
    {!failed && !stats && <div className="detail-card empty">Spielzeit wird geladen …</div>}
    {stats && stats.total_seconds === 0 && <div className="detail-card empty playtime-empty"><Gamepad2 size={34} /><h2>Noch keine Spielzeit erfasst</h2><p>Sobald ein Windows-Agent ein Spiel von Steam, Epic Games, GOG oder der Xbox-App erkennt, erscheint es hier.</p></div>}
    {stats && stats.total_seconds > 0 && <>
      <div className="stats-summary playtime-summary">
        <div><small>Gesamtspielzeit</small><strong>{playtimeShort(stats.total_seconds)}</strong><p>{PERIODS.find((period) => period.days === days)?.label}</p></div>
        <div><small>Meistgespielt</small><strong className="playtime-title">{gameName(top?.title || null)}</strong><p>{top ? playtime(top.seconds) : "—"}</p></div>
        <div><small>Sitzungen</small><strong>{stats.session_count}</strong><p>{stats.game_count} {stats.game_count === 1 ? "Spiel" : "Spiele"}</p></div>
        <div><small>Längste Sitzung</small><strong>{stats.longest_session ? playtimeShort(stats.longest_session.seconds) : "—"}</strong><p>{stats.longest_session ? `${gameName(stats.longest_session.title)} · ${stats.longest_session.node_name || ""}` : ""}</p></div>
      </div>
      <div className="stats-layout">
        <div className="detail-card">
          <ConceptSectionHead eyebrow="Verlauf" title={days && days <= 31 ? "Spielzeit pro Tag" : "Spielzeit pro Monat"} />
          <DailyChart stats={stats} />
        </div>
        <div className="detail-card">
          <ConceptSectionHead eyebrow="Gewohnheiten" title="Wochentag und Uhrzeit" />
          <Heatmap heatmap={stats.heatmap} />
        </div>
      </div>
      <div className="detail-card">
        <ConceptSectionHead eyebrow="Bestenliste" title="Meistgespielte Spiele" aside={<Trophy size={18} />} />
        <div className="game-ranking">{stats.games.map((game, index) => <div className="game-rank" key={game.game_id || "presence"}>
          <span className="rank-number">{String(index + 1).padStart(2, "0")}</span>
          <GameArt gameId={game.game_id} title={game.title} hasArtwork={game.has_artwork} token={token} size="small" />
          <span className="game-rank-name"><b>{gameName(game.title)}</b><small>{[game.launcher ? LAUNCHERS[game.launcher] || game.launcher : null, ...game.genres.slice(0, 2)].filter(Boolean).join(" · ") || "Ohne Titel erfasst"}</small></span>
          <span className="rank-bar"><ConceptMeter value={(game.seconds / topSeconds) * 100} /></span>
          <span className="game-rank-time"><b>{playtime(game.seconds)}</b><small>{game.sessions} {game.sessions === 1 ? "Sitzung" : "Sitzungen"}</small></span>
          {canManage && game.game_id && <button type="button" className="link-button" onClick={() => void correct(game)}>Zuordnung</button>}
        </div>)}</div>
      </div>
      <div className="stats-layout">
        <div className="detail-card">
          <ConceptSectionHead eyebrow="Hardware" title="Werte pro Spiel" aside={<span className="muted-small">Durchschnitt und Höchstwert</span>} />
          {hardwareGames.length ? <div className="table-scroll"><table className="game-hardware">
            <thead><tr><th>Spiel</th><th>CPU-Temp.</th><th>CPU-Leistung</th><th>CPU-Lüfter</th><th>GPU-Temp.</th><th>Hotspot</th><th>GPU-Last</th><th>GPU-Leistung</th><th>RAM</th><th>Energie</th></tr></thead>
            <tbody>{hardwareGames.map((game) => <tr key={game.game_id || "presence"}><td>{game.title}</td><td>{hw(game, "cpu_temperature_c", " °C")}</td><td>{hw(game, "cpu_power_w", " W")}</td><td>{hw(game, "cpu_fan_rpm", "")}</td><td>{hw(game, "gpu_temperature_c", " °C")}</td><td>{hw(game, "gpu_hotspot_c", " °C")}</td><td>{hw(game, "gpu_percent", " %")}</td><td>{hw(game, "gpu_power_w", " W")}</td><td>{hw(game, "ram_temperature_c", " °C")}</td><td>{game.energy_wh ? (game.energy_wh >= 1000 ? `${(game.energy_wh / 1000).toFixed(1)} kWh` : `${Math.round(game.energy_wh)} Wh`) : "—"}</td></tr>)}</tbody>
          </table></div> : <div className="empty">Noch keine Sensordaten aus Spielsitzungen.</div>}
        </div>
        <div className="detail-card">
          <ConceptSectionHead eyebrow="Verlauf" title="Letzte Sitzungen" />
          <div className="session-list">{stats.recent_sessions.map((item) => <div key={item.session_id}>
            <span><b>{gameName(item.title)}</b><small>{item.node_name} · {new Date(item.started_at).toLocaleString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</small></span>
            <em>{playtime(item.seconds)}</em>
          </div>)}</div>
          {stats.nodes.length > 1 && <div className="traffic-breakdown playtime-devices">{stats.nodes.map((entry) => <div key={entry.node_id}><span>{entry.display_name}</span><ConceptMeter value={(entry.seconds / Math.max(stats.total_seconds, 1)) * 100} /><b>{playtime(entry.seconds)}</b></div>)}</div>}
        </div>
      </div>
    </>}
  </>;
}
