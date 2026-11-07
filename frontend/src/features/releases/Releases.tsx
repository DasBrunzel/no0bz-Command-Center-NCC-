import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { POLL, api, qk } from "../../api/endpoints";
import { useNodes } from "../../api/queries";
import type { AgentRelease, FleetNode, UpdateChannel } from "../../api/types";
import { useCan } from "../../app/auth";
import { Icon } from "../../components/Icon";
import { useToast } from "../../components/toast";
import { CopyButton, Dialog, Empty, ErrorState, Lamp, Loading, PageHead, RelTime } from "../../components/ui";
import { fmtBytes } from "../../lib/format";
import { platformLabel, sortByLayout } from "../../lib/node";
import type { Route } from "../../lib/router";
import "./releases.css";

export default function Releases(_: { route: Route }) {
  const can = useCan();
  const releases = useQuery({ queryKey: qk.releases, queryFn: api.releases.list, refetchInterval: POLL.admin });
  const feed = useQuery({ queryKey: qk.releaseFeed, queryFn: api.releases.feed, refetchInterval: POLL.admin });
  const [registering, setRegistering] = useState(false);

  return (
    <div className="releases">
      <PageHead
        title="Releases & Updates"
        lead="Welche Agent-Version wohin geht. Signierte Releases kommen vom GitHub-Feed oder per Manifest."
        actions={can.commander ? <button type="button" className="btn btn-primary" onClick={() => setRegistering(true)}><Icon name="plus" /> Manifest registrieren</button> : <span className="badge">nur lesen</span>}
      />

      <section className="panel feed" aria-labelledby="feed-title">
        <div className="panel-head"><h2 id="feed-title">Release-Feed</h2></div>
        {feed.isPending ? <Loading /> : feed.isError && !feed.data ? (
          <ErrorState onRetry={() => void feed.refetch()}>Der Feed-Status ist nicht abrufbar.</ErrorState>
        ) : (
          <div className="feed-row">
            <Lamp state={!feed.data!.enabled ? "off" : feed.data!.error ? "stop" : "go"} size="l" />
            <div>
              <p><b>{feed.data!.enabled ? `Folgt ${feed.data!.repository}` : "Feed ist ausgeschaltet"}</b></p>
              <p className="small ink-2">
                {feed.data!.checked_at ? <>Zuletzt geprüft <RelTime iso={feed.data!.checked_at} /></> : "Noch nicht geprüft"}
                {feed.data!.registered.length ? ` · übernommen: ${feed.data!.registered.join(", ")}` : ""}
              </p>
              {feed.data!.error && <p className="form-error">{feed.data!.error}</p>}
            </div>
          </div>
        )}
      </section>

      <section className="panel section" aria-labelledby="list-title">
        <div className="panel-head"><h2 id="list-title">Registrierte Releases</h2></div>
        {releases.isPending ? <Loading /> : releases.isError && !releases.data ? (
          <ErrorState onRetry={() => void releases.refetch()}>Die Releases konnten nicht geladen werden.</ErrorState>
        ) : !releases.data?.length ? (
          <Empty title="Noch kein Release" icon="releases">Sobald der Feed ein signiertes Release findet oder ein Manifest registriert wird, steht es hier.</Empty>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Version</th><th>Kanal</th><th>Plattform</th><th className="r">Größe</th><th>Veröffentlicht</th><th className="r">Geräte</th><th>Prüfsumme</th></tr></thead>
              <tbody>
                {releases.data.map((release) => (
                  <tr key={release.release_id}>
                    <td><a href={release.artifact_url} target="_blank" rel="noopener noreferrer"><b>{release.payload_version}</b></a>{release.minimum_core_version && <small className="ink-3"> · ab Core {release.minimum_core_version}</small>}</td>
                    <td><span className="badge" data-tone={release.channel === "beta" ? "shunt" : "go"}>{release.channel === "beta" ? "Beta" : "Stabil"}</span></td>
                    <td>{release.platform === "windows" ? "Windows" : "Linux"} · {release.architecture}</td>
                    <td className="r">{fmtBytes(release.size_bytes)}</td>
                    <td><RelTime iso={release.released_at} /></td>
                    <td className="r">{release.assigned_nodes}</td>
                    <td><span className="row nowrap"><code className="xsmall" title={release.sha256}>{release.sha256.slice(0, 12)}…</code><CopyButton value={release.sha256} label="SHA-256" /></span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <Assignment releases={releases.data ?? []} />
      {registering && <RegisterDialog onClose={() => setRegistering(false)} />}
    </div>
  );
}

function Assignment({ releases }: { releases: AgentRelease[] }) {
  const nodes = useNodes();
  const list = [...(nodes.data ?? [])].sort(sortByLayout);
  return (
    <section className="panel section" aria-labelledby="assign-title">
      <div className="panel-head"><h2 id="assign-title">Zuweisung pro Gerät</h2><p>Kanal und optional ein festes Release</p></div>
      {nodes.isPending ? <Loading /> : list.length === 0 ? <p className="ink-3 small">Keine Geräte.</p> : (
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>Gerät</th><th>Installiert</th><th>Kanal</th><th>Release</th><th>Angeboten</th></tr></thead>
            <tbody>{list.map((node) => <AssignmentRow key={node.node_id} node={node} releases={releases} />)}</tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function AssignmentRow({ node, releases }: { node: FleetNode; releases: AgentRelease[] }) {
  const can = useCan();
  const client = useQueryClient();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const platform = node.platform.toLowerCase().startsWith("win") ? "windows" : "linux";
  const compatible = releases.filter((release) => release.platform === platform);
  const run = async (action: () => Promise<unknown>, success: string) => {
    setBusy(true);
    try {
      await action();
      await Promise.all([client.invalidateQueries({ queryKey: qk.nodes }), client.invalidateQueries({ queryKey: qk.releases })]);
      toast.ok(success);
    } catch (error) {
      toast.fail(error);
    } finally {
      setBusy(false);
    }
  };
  const locked = !can.commander || busy;
  return (
    <tr>
      <td><b>{node.display_name}</b> <small className="ink-3">{platformLabel(node)}</small></td>
      <td>{node.agent_version ?? "–"}</td>
      <td>
        <label className="visually-hidden" htmlFor={`ch-${node.node_id}`}>Kanal für {node.display_name}</label>
        <select id={`ch-${node.node_id}`} className="select select-s" value={node.update_channel} disabled={locked} onChange={(event) => void run(() => api.releases.setChannel(node.node_id, event.target.value as UpdateChannel), `${node.display_name}: Kanal geändert.`)}>
          <option value="stable">Stabil</option>
          <option value="beta">Beta</option>
        </select>
      </td>
      <td>
        <label className="visually-hidden" htmlFor={`rel-${node.node_id}`}>Release für {node.display_name}</label>
        <select id={`rel-${node.node_id}`} className="select select-s" value={node.pending_release_id ?? ""} disabled={locked} onChange={(event) => void run(() => api.releases.assign(node.node_id, event.target.value || null, node.release_allow_downgrade), event.target.value ? `${node.display_name}: Release festgelegt.` : `${node.display_name} folgt wieder dem Kanal.`)}>
          <option value="">neuestes im Kanal</option>
          {compatible.map((release) => <option key={release.release_id} value={release.release_id}>{release.payload_version} ({release.channel})</option>)}
        </select>
      </td>
      <td>{node.release_target_version ?? <span className="ink-3">aktuell</span>}{node.release_pin_held_back && <span className="badge" data-tone="caution" style={{ marginInlineStart: 6 }}>zurückgehalten</span>}</td>
    </tr>
  );
}

function RegisterDialog({ onClose }: { onClose: () => void }) {
  const client = useQueryClient();
  const toast = useToast();
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    let manifest: unknown;
    try {
      manifest = JSON.parse(text);
    } catch {
      setError("Das ist kein gültiges JSON.");
      return;
    }
    if (!manifest || typeof manifest !== "object" || Array.isArray(manifest)) {
      setError("Das Manifest muss ein JSON-Objekt sein.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const release = await api.releases.create(manifest as Record<string, unknown>);
      await client.invalidateQueries({ queryKey: qk.releases });
      toast.ok(`Release ${release.payload_version} registriert.`);
      onClose();
    } catch (failure) {
      toast.fail(failure, "Das Manifest wurde abgelehnt.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title="Release per Manifest registrieren"
      footer={<><button type="button" className="btn" onClick={onClose}>Abbrechen</button><button type="button" className="btn btn-primary" disabled={busy || !text.trim()} onClick={() => void submit()}>Registrieren</button></>}
    >
      <p className="small">Das Manifest erzeugt <code>build_ncc_payload.ps1</code>. Die Datei selbst bleibt unter ihrer HTTPS-Adresse, der Server prüft Signatur und Prüfsumme.</p>
      <label className="field">
        <span>Manifest-Datei</span>
        <input className="input" type="file" accept="application/json,.json" onChange={(event) => { const file = event.target.files?.[0]; if (file) void file.text().then(setText); }} />
      </label>
      <label className="field">
        <span>oder JSON einfügen</span>
        <textarea className="textarea code" rows={10} value={text} onChange={(event) => setText(event.target.value)} spellCheck={false} placeholder='{ "payload_version": "0.6.2", … }' />
      </label>
      {error && <p className="form-error" role="alert">{error}</p>}
    </Dialog>
  );
}
