import { useMemo, useState } from "react";
import { useGameStats, useGames, useNodes } from "../../api/queries";
import type { Game } from "../../api/types";
import { useCan } from "../../app/auth";
import { Columns, Heatmap } from "../../components/charts";
import { DaysPicker, Empty, ErrorState, Loading, PageHead, RelTime } from "../../components/ui";
import { fmtDay, fmtDuration, fmtHours, fmtInt, fmt1 } from "../../lib/format";
import { sortByLayout } from "../../lib/node";
import type { Route } from "../../lib/router";
import { Artwork } from "./Artwork";
import { GameDialog } from "./GameDialog";
import "./games.css";

export default function Games(_: { route: Route }) {
  const [days, setDays] = useState(30);
  const [nodeId, setNodeId] = useState("");
  const [open, setOpen] = useState<Game | null>(null);
  const stats = useGameStats(days, nodeId || null);
  const library = useGames();
  const nodes = useNodes();
  const can = useCan();
  const byId = useMemo(() => new Map((library.data ?? []).map((game) => [game.game_id, game])), [library.data]);
  const s = stats.data;
  const top = s ? Math.max(1, ...s.games.map((game) => game.seconds)) : 1;
  const nodeTop = s ? Math.max(1, ...s.nodes.map((node) => node.seconds)) : 1;

  return (
    <div className="games">
      <PageHead title="Spiele" lead="Wer hat was wie lange gezockt – aus den Sitzungen, die die Agenten melden." />
      <div className="filters">
        <DaysPicker value={days} onChange={setDays} />
        <label className="field">
          <span className="visually-hidden">Gerät</span>
          <select className="select" value={nodeId} onChange={(event) => setNodeId(event.target.value)}>
            <option value="">Alle Geräte</option>
            {[...(nodes.data ?? [])].sort(sortByLayout).map((node) => <option key={node.node_id} value={node.node_id}>{node.display_name}</option>)}
          </select>
        </label>
      </div>

      {stats.isPending ? (
        <Loading label="Spielzeit wird geladen" />
      ) : stats.isError && !s ? (
        <ErrorState onRetry={() => void stats.refetch()}>Die Spielzeit-Statistik konnte nicht geladen werden.</ErrorState>
      ) : !s || s.session_count === 0 ? (
        <Empty title="Noch keine Spiele erkannt" icon="games">
          In diesem Zeitraum hat kein Agent eine Spielsitzung gemeldet. Läuft auf den PCs die Spielerfassung? Das lässt sich pro Gerät unter Geräte › Spiele einstellen.
        </Empty>
      ) : (
        <div className="stack" data-refreshing={stats.isPlaceholderData || undefined}>
          <dl className="play-facts">
            <div><dt>Gespielt</dt><dd>{fmtHours(s.total_seconds)}</dd></div>
            <div><dt>Sitzungen</dt><dd>{fmtInt(s.session_count)}</dd></div>
            <div><dt>Verschiedene Spiele</dt><dd>{fmtInt(s.game_count)}</dd></div>
            {s.longest_session && (
              <div className="play-longest">
                <dt>Längste Sitzung</dt>
                <dd>
                  {fmtDuration(s.longest_session.seconds)}
                  <small>{s.longest_session.title ?? "Unbekannt"} auf {s.longest_session.node_name ?? "?"}, <RelTime iso={s.longest_session.started_at} /></small>
                </dd>
              </div>
            )}
          </dl>

          <section className="panel" aria-labelledby="ranking-title">
            <div className="panel-head"><h2 id="ranking-title">Rangliste</h2><p>nach Spielzeit</p></div>
            <ol className="ranking plain" role="list">
              {s.games.map((game, index) => {
                const known = game.game_id ? byId.get(game.game_id) : undefined;
                return (
                  <li key={game.game_id ?? `unknown-${index}`}>
                    <span className="ranking-place num" aria-label={`Platz ${index + 1}`}>{index + 1}</span>
                    <Artwork gameId={game.game_id} title={game.title} hasArtwork={game.has_artwork} size="thumb" />
                    <div className="ranking-body">
                      <div className="ranking-title">
                        {known ? (
                          <button type="button" className="link-button" onClick={() => setOpen(known)}>{game.title ?? "Unbekanntes Spiel"}</button>
                        ) : (
                          <b>{game.title ?? "Unbekanntes Spiel"}</b>
                        )}
                        <span className="ink-3 xsmall">{launcherName(game.launcher)} · {game.sessions} {game.sessions === 1 ? "Sitzung" : "Sitzungen"} · zuletzt <RelTime iso={game.last_played_at} /></span>
                      </div>
                      <div className="hbar" aria-hidden="true"><span style={{ inlineSize: `${(game.seconds / top) * 100}%` }} /></div>
                    </div>
                    <span className="ranking-value num">{fmtHours(game.seconds)}{game.energy_wh ? <small>{fmt1(game.energy_wh / 1000)} kWh</small> : null}</span>
                  </li>
                );
              })}
            </ol>
          </section>

          <div className="games-split">
            <section className="panel" aria-labelledby="daily-title">
              <div className="panel-head"><h2 id="daily-title">Spielzeit pro Tag</h2></div>
              <Columns
                title="Spielzeit pro Tag in Stunden"
                unit="h"
                items={s.daily.map((day) => ({ label: fmtDay(day.date), value: day.seconds / 3600 }))}
                format={(value) => fmt1(value)}
              />
            </section>
            <section className="panel" aria-labelledby="nodes-title">
              <div className="panel-head"><h2 id="nodes-title">Nach Gerät</h2></div>
              <ul className="plain node-bars" role="list">
                {s.nodes.map((node) => (
                  <li key={node.node_id}>
                    <span>{node.display_name}</span>
                    <div className="hbar" aria-hidden="true"><span style={{ inlineSize: `${(node.seconds / nodeTop) * 100}%` }} /></div>
                    <span className="num">{fmtHours(node.seconds)}</span>
                  </li>
                ))}
              </ul>
            </section>
          </div>

          <section className="panel" aria-labelledby="heat-title">
            <div className="panel-head"><h2 id="heat-title">Wann gespielt wird</h2><p>Wochentag × Uhrzeit, deine Zeitzone</p></div>
            <Heatmap rows={s.heatmap} title="Spielzeit nach Wochentag und Stunde" format={(seconds) => fmtDuration(seconds)} />
          </section>

          <section className="panel" aria-labelledby="recent-title">
            <div className="panel-head"><h2 id="recent-title">Letzte Sitzungen</h2></div>
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>Spiel</th><th>Gerät</th><th>Beginn</th><th className="r">Dauer</th></tr></thead>
                <tbody>
                  {s.recent_sessions.map((item) => (
                    <tr key={item.session_id}>
                      <td>{item.title ?? "Unbekannt"}</td>
                      <td>{item.node_name}</td>
                      <td><RelTime iso={item.started_at} /></td>
                      <td className="r">{fmtDuration(item.seconds)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}

      <section className="section mt-5" aria-labelledby="library-title">
        <div className="section-title">
          <h2 id="library-title">Bibliothek</h2>
          <p>{[library.data ? `${library.data.length} erkannte Spiele` : null, can.commander ? "Banner und Steam-Zuordnung über das Spiel" : null].filter(Boolean).join(" · ")}</p>
        </div>
        {library.isPending ? <Loading /> : library.isError && !library.data ? (
          <ErrorState onRetry={() => void library.refetch()}>Die Spieleliste konnte nicht geladen werden.</ErrorState>
        ) : !library.data?.length ? (
          <Empty title="Noch keine Spiele erkannt" icon="games">Sobald ein Agent ein Spiel meldet, landet es hier.</Empty>
        ) : (
          <ul className="library plain" role="list">
            {library.data.map((game) => (
              <li key={game.game_id}>
                <button type="button" className="library-item" onClick={() => setOpen(game)}>
                  <Artwork gameId={game.game_id} title={game.title} hasArtwork={game.has_artwork} />
                  <span className="library-meta">
                    <b>{game.title}</b>
                    <small>{launcherName(game.launcher)}{game.match_state !== "matched" ? " · ohne Store-Daten" : ""}</small>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {open && <GameDialog game={byId.get(open.game_id) ?? open} onClose={() => setOpen(null)} />}
    </div>
  );
}

export function launcherName(launcher: string | null | undefined): string {
  const names: Record<string, string> = { steam: "Steam", battlenet: "Battle.net", epic: "Epic", gog: "GOG", ea: "EA App", ubisoft: "Ubisoft Connect", xbox: "Xbox", riot: "Riot", lutris: "Lutris", heroic: "Heroic" };
  return launcher ? names[launcher.toLowerCase()] ?? launcher : "Unbekannt";
}
