import { useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { api, qk } from "../../api/endpoints";
import type { Game } from "../../api/types";
import { useCan } from "../../app/auth";
import { Icon } from "../../components/Icon";
import { useToast } from "../../components/toast";
import { Dialog } from "../../components/ui";
import { Artwork, bumpArtwork } from "./Artwork";
import { launcherName } from "./Games";

const WIDTH = 920;
const HEIGHT = 430;
const MAX_BYTES = 2 * 1024 * 1024;

/** Crop any picture to the Steam banner format (cover), as JPEG. */
async function cropBanner(file: File): Promise<Blob> {
  const bitmap = await createImageBitmap(file);
  const canvas = document.createElement("canvas");
  canvas.width = WIDTH;
  canvas.height = HEIGHT;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("canvas");
  const scale = Math.max(WIDTH / bitmap.width, HEIGHT / bitmap.height);
  const w = bitmap.width * scale;
  const h = bitmap.height * scale;
  context.drawImage(bitmap, (WIDTH - w) / 2, (HEIGHT - h) / 2, w, h);
  bitmap.close();
  return new Promise((resolve, reject) => canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("encode"))), "image/jpeg", 0.88));
}

export function GameDialog({ game, onClose }: { game: Game; onClose: () => void }) {
  const can = useCan();
  const client = useQueryClient();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<{ url: string; blob: Blob } | null>(null);
  const [steamId, setSteamId] = useState(game.steam_app_id ? String(game.steam_app_id) : "");

  const refresh = async () => {
    bumpArtwork(game.game_id);
    await Promise.all([client.invalidateQueries({ queryKey: qk.games }), client.invalidateQueries({ queryKey: ["games", "stats"] })]);
  };

  const choose = async (file: File | undefined) => {
    if (!file) return;
    if (!/^image\/(jpeg|png|webp)$/.test(file.type)) {
      toast.notify("Bitte ein JPEG-, PNG- oder WebP-Bild wählen.", "stop");
      return;
    }
    try {
      const blob = await cropBanner(file);
      if (blob.size > MAX_BYTES) {
        toast.notify("Das zugeschnittene Bild ist größer als 2 MB.", "stop");
        return;
      }
      if (preview) URL.revokeObjectURL(preview.url);
      setPreview({ url: URL.createObjectURL(blob), blob });
    } catch {
      toast.notify("Das Bild konnte nicht gelesen werden.", "stop");
    }
  };

  const run = async (action: () => Promise<unknown>, success: string) => {
    setBusy(true);
    try {
      await action();
      await refresh();
      toast.ok(success);
      if (preview) { URL.revokeObjectURL(preview.url); setPreview(null); }
    } catch (error) {
      toast.fail(error);
    } finally {
      setBusy(false);
    }
  };

  const gridSearch = `https://www.steamgriddb.com/search/grids?term=${encodeURIComponent(game.title)}`;

  return (
    <Dialog open wide onClose={onClose} title={game.title}>
      <div className="game-dialog">
        <div className="stack">
          {preview ? (
            <div className="artwork"><img src={preview.url} alt="Vorschau des neuen Banners" width={WIDTH} height={HEIGHT} /></div>
          ) : (
            <Artwork gameId={game.game_id} title={game.title} hasArtwork={game.has_artwork} />
          )}
          {can.commander ? (
            <div className="stack-s">
              <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={(event) => void choose(event.target.files?.[0])} />
              <div className="actions">
                {preview ? (
                  <>
                    <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void run(() => api.games.uploadArtwork(game.game_id, preview.blob), "Banner gespeichert.")}><Icon name="upload" /> Banner speichern</button>
                    <button type="button" className="btn" onClick={() => { URL.revokeObjectURL(preview.url); setPreview(null); }}>Verwerfen</button>
                  </>
                ) : (
                  <>
                    <button type="button" className="btn" onClick={() => input.current?.click()}><Icon name="upload" /> {game.artwork_source === "upload" ? "Banner ersetzen" : "Banner hochladen"}</button>
                    {game.has_artwork && game.artwork_source === "upload" && (
                      <button type="button" className="btn btn-danger" disabled={busy} onClick={() => void run(() => api.games.removeArtwork(game.game_id), "Eigener Banner entfernt.")}><Icon name="trash" /> Banner entfernen</button>
                    )}
                  </>
                )}
              </div>
              <p className="form-hint">
                Das Bild wird hier auf 920 × 430 zugeschnitten. Passende Banner findest du bei{" "}
                <a href={gridSearch} target="_blank" rel="noopener noreferrer">SteamGridDB <Icon name="external" size={14} style={{ display: "inline", verticalAlign: "-2px" }} /></a>
                {" "}– herunterladen, hier hochladen.
              </p>
            </div>
          ) : (
            <p className="form-hint">Banner und Zuordnung ändern dürfen Commander.</p>
          )}
        </div>

        <div className="stack">
          <dl className="kv">
            <dt>Launcher</dt><dd>{launcherName(game.launcher)}</dd>
            <dt>Store-Daten</dt><dd>{game.match_state === "matched" ? `${game.store_name ?? game.title}${game.manual_match ? " (von Hand)" : ""}` : "keine gefunden"}</dd>
            {game.developers.length > 0 && <><dt>Entwickler</dt><dd>{game.developers.join(", ")}</dd></>}
            {game.genres.length > 0 && <><dt>Genres</dt><dd>{game.genres.join(", ")}</dd></>}
            {game.release_date && <><dt>Erschienen</dt><dd>{game.release_date}</dd></>}
            <dt>Banner</dt><dd>{game.has_artwork ? (game.artwork_source === "upload" ? "eigener Upload" : game.artwork_source === "steamgriddb" ? "SteamGridDB" : "Steam") : "keiner"}</dd>
          </dl>
          {game.description && <p className="small ink-2">{game.description}</p>}
          {can.commander && (
            <form className="stack-s" onSubmit={(event) => { event.preventDefault(); const value = steamId.trim() ? Number(steamId) : null; void run(() => api.games.update(game.game_id, value), value ? "Steam-Zuordnung gespeichert." : "Steam-Zuordnung entfernt."); }}>
              <label className="field">
                <span>Steam-App-ID</span>
                <input className="input" inputMode="numeric" pattern="[0-9]{0,8}" value={steamId} onChange={(event) => setSteamId(event.target.value.replace(/\D/g, ""))} placeholder="leer = nicht auf Steam" />
                <small>Steht in der Store-Adresse, z. B. store.steampowered.com/app/<b>548430</b>.</small>
              </label>
              <div className="actions"><button type="submit" className="btn" disabled={busy}>Zuordnung speichern</button></div>
            </form>
          )}
        </div>
      </div>
    </Dialog>
  );
}
