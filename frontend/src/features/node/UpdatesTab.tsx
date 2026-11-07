import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, qk } from "../../api/endpoints";
import type { FleetNode, UpdateChannel } from "../../api/types";
import { useCan } from "../../app/auth";
import { Icon } from "../../components/Icon";
import { useToast } from "../../components/toast";
import { RelTime } from "../../components/ui";

export default function UpdatesTab({ node }: { node: FleetNode }) {
  const can = useCan();
  const client = useQueryClient();
  const toast = useToast();
  const releases = useQuery({ queryKey: qk.releases, queryFn: api.releases.list, enabled: can.team });
  const [busy, setBusy] = useState(false);
  const [releaseId, setReleaseId] = useState(node.pending_release_id ?? "");
  const [downgrade, setDowngrade] = useState(node.release_allow_downgrade);
  const platform = node.platform.toLowerCase().startsWith("win") ? "windows" : "linux";
  const compatible = (releases.data ?? []).filter((release) => release.platform === platform);
  const pinned = compatible.find((release) => release.release_id === node.pending_release_id);

  const refresh = async () => {
    await Promise.all([client.invalidateQueries({ queryKey: qk.node(node.node_id) }), client.invalidateQueries({ queryKey: qk.nodes }), client.invalidateQueries({ queryKey: qk.releases })]);
  };
  const run = async (action: () => Promise<unknown>, success: string) => {
    setBusy(true);
    try {
      await action();
      await refresh();
      toast.ok(success);
    } catch (error) {
      toast.fail(error);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      <section className="panel">
        <div className="panel-head"><h2>Agent</h2></div>
        <dl className="kv">
          <dt>Installiert</dt><dd>{node.agent_version ?? "unbekannt"}</dd>
          <dt>Angeboten</dt><dd>{node.release_target_version ? <b>{node.release_target_version}</b> : "nichts – aktuell"}</dd>
          <dt>Kanal</dt><dd>{node.update_channel === "beta" ? "Beta" : "Stabil"}</dd>
          <dt>Festgelegt auf</dt><dd>{pinned ? `${pinned.payload_version} (${pinned.channel})` : node.pending_release_id ? "ein Release" : "neuestes im Kanal"}</dd>
          {node.release_pin_held_back && <><dt>Hinweis</dt><dd className="ink-2">Das festgelegte Release ist älter als die installierte Version und wird zurückgehalten, bis ein Downgrade erlaubt ist.</dd></>}
          <dt>Letzte Prüfung angefragt</dt><dd>{node.update_check_requested_at ? <RelTime iso={node.update_check_requested_at} /> : "nie"}</dd>
        </dl>
        <div className="actions mt-4">
          <button
            type="button"
            className="btn"
            disabled={busy || !can.manage(node)}
            title={can.manage(node) ? undefined : "Nur Commander oder der Besitzer des Geräts."}
            onClick={() => void run(() => api.fleet.requestUpdateCheck(node.node_id), "Update-Prüfung angefragt. Der Agent prüft beim nächsten Heartbeat.")}
          >
            <Icon name="refresh" /> Jetzt auf Updates prüfen
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head"><h2>Update-Kanal</h2>{!can.commander && <span className="badge">nur Commander</span>}</div>
        <div className="segmented" role="radiogroup" aria-label="Update-Kanal">
          {(["stable", "beta"] as UpdateChannel[]).map((channel) => (
            <label key={channel}>
              <input type="radio" name="channel" checked={node.update_channel === channel} disabled={!can.commander || busy} onChange={() => void run(() => api.fleet.setUpdateChannel(node.node_id, channel), `Kanal auf ${channel === "beta" ? "Beta" : "Stabil"} gestellt.`)} />
              <span>{channel === "beta" ? "Beta" : "Stabil"}</span>
            </label>
          ))}
        </div>
        <p className="form-hint mt-4">Beta bekommt neue Agent-Versionen früher – gut für Testgeräte.</p>
      </section>

      {can.team && (
        <section className="panel">
          <div className="panel-head"><h2>Release festlegen</h2>{!can.commander && <span className="badge">nur Commander</span>}</div>
          <form className="stack" onSubmit={(event) => { event.preventDefault(); void run(() => api.fleet.assignRelease(node.node_id, releaseId || null, downgrade), releaseId ? "Release zugewiesen." : "Gerät folgt wieder dem neuesten Release."); }}>
            <label className="field">
              <span>Release für {platform === "windows" ? "Windows" : "Linux"}</span>
              <select className="select" value={releaseId} disabled={!can.commander || busy} onChange={(event) => setReleaseId(event.target.value)}>
                <option value="">Automatisch: neuestes im Kanal</option>
                {compatible.map((release) => <option key={release.release_id} value={release.release_id}>{release.payload_version} · {release.channel} · {release.architecture}</option>)}
              </select>
              {compatible.length === 0 && <small>Für diese Plattform ist noch kein Release registriert.</small>}
            </label>
            <label className="switch">
              <input type="checkbox" checked={downgrade} disabled={!can.commander || busy} onChange={(event) => setDowngrade(event.target.checked)} />
              Ältere Version erlauben (Downgrade)
            </label>
            <div className="actions"><button type="submit" className="btn btn-primary" disabled={!can.commander || busy}>Festlegen</button></div>
          </form>
        </section>
      )}
    </div>
  );
}
