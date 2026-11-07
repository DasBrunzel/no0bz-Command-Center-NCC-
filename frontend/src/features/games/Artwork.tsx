import "./games.css";
import { useEffect, useState } from "react";
import { hasLegacyToken } from "../../api/client";
import { api } from "../../api/endpoints";

/** Cache-busting revision per game, bumped after an upload or removal. */
const revisions = new Map<string, number>();
export function bumpArtwork(gameId: string): void {
  revisions.set(gameId, (revisions.get(gameId) ?? 0) + 1);
}

/**
 * Game banner. With the session cookie a plain <img> works; with the legacy
 * token header the image is fetched and shown from a blob URL.
 */
export function Artwork({ gameId, title, hasArtwork, size = "banner" }: { gameId: string | null; title: string | null; hasArtwork: boolean; size?: "banner" | "thumb" }) {
  const [failed, setFailed] = useState(false);
  const [blob, setBlob] = useState<string | null>(null);
  const revision = gameId ? revisions.get(gameId) ?? 0 : 0;
  const useBlob = hasLegacyToken();

  useEffect(() => {
    setFailed(false);
    if (!gameId || !hasArtwork || !useBlob) return;
    const controller = new AbortController();
    let url: string | null = null;
    api.games.artwork(gameId, controller.signal)
      .then((response) => response.blob())
      .then((data) => { url = URL.createObjectURL(data); setBlob(url); })
      .catch(() => setFailed(true));
    return () => { controller.abort(); if (url) URL.revokeObjectURL(url); };
  }, [gameId, hasArtwork, useBlob, revision]);

  const initials = (title ?? "?").split(/\s+/).filter(Boolean).slice(0, 2).map((word) => word[0]).join("").toUpperCase();
  if (!gameId || !hasArtwork || failed) {
    return (
      <div className={`artwork artwork-${size} artwork-empty`} aria-hidden="true">
        <span>{initials || "?"}</span>
      </div>
    );
  }
  const src = useBlob ? blob : `${api.games.artworkUrl(gameId)}${revision ? `?v=${revision}` : ""}`;
  return (
    <div className={`artwork artwork-${size}`}>
      {src && <img src={src} alt={title ? `Banner von ${title}` : ""} loading="lazy" decoding="async" width={920} height={430} onError={() => setFailed(true)} />}
    </div>
  );
}
