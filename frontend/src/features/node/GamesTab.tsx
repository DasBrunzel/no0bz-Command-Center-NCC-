import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, qk } from "../../api/endpoints";
import { useGameStats } from "../../api/queries";
import type { FleetNode, GameTracking } from "../../api/types";
import { useCan } from "../../app/auth";
import { useToast } from "../../components/toast";
import { Loading, RelTime } from "../../components/ui";
import { fmtDuration, fmtHours, fmtTime } from "../../lib/format";
import { Artwork } from "../games/Artwork";

const TRACKING: Array<{ value: GameTracking; label: string; hint: string }> = [
  { value: "titles", label: "Spiele mit Titel", hint: "NCC merkt sich, welches Spiel wie lange lief." },
  { value: "presence", label: "Nur „spielt gerade“", hint: "Zeigt, dass gespielt wird, aber nicht was." },
  { value: "off", label: "Aus", hint: "Keine Spielerfassung auf diesem Gerät." },
];

export default function GamesTab({ node }: { node: FleetNode }) {
  const can = useCan();
  const client = useQueryClient();
  const toast = useToast();
  const stats = useGameStats(30, node.node_id);
  const [busy, setBusy] = useState(false);
  const editable = can.manage(node);
  const playing = node.online ? node.now_playing : null;

  const save = async (tracking: GameTracking, auto: boolean) => {
    setBusy(true);
    try {
      const updated = await api.games.setNodeSettings(node.node_id, tracking, auto);
      client.setQueryData(qk.node(node.node_id), updated);
      await client.invalidateQueries({ queryKey: qk.nodes });
      toast.ok("Spiel-Einstellungen gespeichert.");
    } catch (error) {
      toast.fail(error, "Die Spiel-Einstellungen konnten nicht gespeichert werden.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      {playing ? (
        <section className="now-playing">
          <Artwork gameId={playing.game_id} title={playing.title} hasArtwork={playing.has_artwork} />
          <div>
            <p className="ink-3 small">Läuft gerade seit {fmtTime(playing.started_at)} Uhr</p>
            <h2>{playing.title ?? "Ein Spiel"}</h2>
            <p className="small">{playing.launcher ?? ""}{playing.genres.length ? ` · ${playing.genres.join(", ")}` : ""}</p>
          </div>
        </section>
      ) : null}

      <section className="panel" aria-labelledby="game-settings">
        <div className="panel-head"><h2 id="game-settings">Spielerfassung</h2>{!editable && <span className="badge">nur lesen</span>}</div>
        <fieldset className="radio-cards" disabled={!editable || busy}>
          <legend className="visually-hidden">Was soll erfasst werden?</legend>
          {TRACKING.map((option) => (
            <label key={option.value} className="radio-card">
              <input type="radio" name="tracking" checked={node.game_tracking === option.value} onChange={() => void save(option.value, node.auto_gaming_mode)} />
              <span><b>{option.label}</b><small>{option.hint}</small></span>
            </label>
          ))}
        </fieldset>
        <label className="switch mt-4">
          <input type="checkbox" checked={node.auto_gaming_mode} disabled={!editable || busy || node.game_tracking === "off"} onChange={(event) => void save(node.game_tracking, event.target.checked)} />
          Gaming Mode automatisch einschalten, solange ein Spiel läuft
        </label>
        {!editable && <p className="form-hint mt-4">Ändern dürfen Commander und der Besitzer des Geräts.</p>}
      </section>

      <section className="panel" aria-labelledby="node-games">
        <div className="panel-head"><h2 id="node-games">Gespielt in den letzten 30 Tagen</h2>{stats.data && <p>{fmtHours(stats.data.total_seconds)} in {stats.data.session_count} Sitzungen</p>}</div>
        {stats.isPending ? <Loading /> : !stats.data || stats.data.games.length === 0 ? (
          <p className="ink-3 small">{node.game_tracking === "off" ? "Die Spielerfassung ist aus." : "Noch keine Spiele erkannt."}</p>
        ) : (
          <table className="table">
            <thead><tr><th>Spiel</th><th className="r">Spielzeit</th><th className="r">Sitzungen</th><th className="r">Zuletzt</th></tr></thead>
            <tbody>
              {stats.data.games.map((game) => (
                <tr key={game.game_id ?? "unknown"}>
                  <td>{game.title ?? "Unbekanntes Spiel"}</td>
                  <td className="r">{fmtDuration(game.seconds)}</td>
                  <td className="r">{game.sessions}</td>
                  <td className="r"><RelTime iso={game.last_played_at} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
