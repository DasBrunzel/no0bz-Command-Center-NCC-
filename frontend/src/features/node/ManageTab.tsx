import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, qk } from "../../api/endpoints";
import { useNodes, usePhysical } from "../../api/queries";
import type { AccessRole, FleetNode } from "../../api/types";
import { roleLabel, useCan } from "../../app/auth";
import { Icon } from "../../components/Icon";
import { useToast } from "../../components/toast";
import { Dialog } from "../../components/ui";
import { platformLabel } from "../../lib/node";
import { navigate } from "../../lib/router";

export default function ManageTab({ node, siblings }: { node: FleetNode; siblings: FleetNode[] }) {
  const can = useCan();
  const client = useQueryClient();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState(node.display_name);
  const users = useQuery({ queryKey: qk.users, queryFn: api.users.list, enabled: can.commander });
  const manageable = can.manage(node);

  const refresh = () => Promise.all([
    client.invalidateQueries({ queryKey: qk.node(node.node_id) }),
    client.invalidateQueries({ queryKey: qk.nodes }),
    client.invalidateQueries({ queryKey: qk.physical }),
  ]);
  const run = async (action: () => Promise<unknown>, success: string) => {
    setBusy(true);
    try {
      await action();
      await refresh();
      toast.ok(success);
      return true;
    } catch (error) {
      toast.fail(error);
      return false;
    } finally {
      setBusy(false);
    }
  };

  const rename = (event: FormEvent) => {
    event.preventDefault();
    const value = name.trim().replace(/\s+/g, " ");
    if (!value || value === node.display_name) return;
    void run(() => api.fleet.rename(node.node_id, value), `Umbenannt in „${value}“.`);
  };

  if (!manageable && !can.commander) {
    return (
      <section className="panel">
        <div className="panel-head"><h2>Verwaltung</h2><span className="badge">nur lesen</span></div>
        <p className="small">{can.beta ? "Als Beta-Tester siehst du alles, änderst aber nichts. Name, Besitzer, Rolle und Dualboot verwaltet ein Commander." : "Verwalten darf nur ein Commander oder der Besitzer dieses Geräts."}</p>
        <dl className="kv mt-4">
          <dt>Name</dt><dd>{node.display_name}</dd>
          <dt>Rolle des Agenten</dt><dd>{roleLabel(node.access_role)}</dd>
          <dt>Besitzer</dt><dd>{node.owner_name ?? "niemand"}</dd>
          <dt>Physisches Gerät</dt><dd>{node.physical_device_name ?? "eigenständig"}</dd>
        </dl>
      </section>
    );
  }

  return (
    <div className="stack">
      <section className="panel">
        <div className="panel-head"><h2>Name</h2></div>
        <form className="row" onSubmit={rename}>
          <label className="field grow">
            <span className="visually-hidden">Anzeigename</span>
            <input className="input" maxLength={128} required value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <button type="submit" className="btn btn-primary" disabled={busy || !name.trim() || name.trim() === node.display_name}>Umbenennen</button>
        </form>
      </section>

      {can.commander && (
        <section className="panel">
          <div className="panel-head"><h2>Zugriff</h2></div>
          <div className="form-grid">
            <label className="field">
              <span>Rolle des Agenten</span>
              <select className="select" value={node.access_role} disabled={busy} onChange={(event) => void run(() => api.fleet.setRole(node.node_id, event.target.value as AccessRole), "Rolle geändert.")}>
                <option value="commander">Commander</option>
                <option value="beta_tester">Beta-Tester</option>
              </select>
              <small>Bestimmt, was der Agent dieses Geräts am Server darf.</small>
            </label>
            <label className="field">
              <span>Besitzer</span>
              <select className="select" value={node.owner_user_id ?? ""} disabled={busy || users.isPending} onChange={(event) => void run(() => api.fleet.setOwner(node.node_id, event.target.value || null), event.target.value ? "Besitzer gesetzt." : "Besitzer entfernt.")}>
                <option value="">niemand</option>
                {(users.data ?? []).filter((user) => user.user_id && user.active).map((user) => <option key={user.user_id} value={user.user_id!}>{user.username} ({roleLabel(user.role)})</option>)}
              </select>
              <small>Ein Freund sieht nur Geräte, die ihm gehören, und darf sie selbst verwalten.</small>
            </label>
          </div>
        </section>
      )}

      {can.commander && <DualBoot node={node} siblings={siblings} busy={busy} run={run} />}

      {can.commander && <DangerZone node={node} />}
    </div>
  );
}

function DualBoot({ node, siblings, busy, run }: { node: FleetNode; siblings: FleetNode[]; busy: boolean; run: (action: () => Promise<unknown>, success: string) => Promise<boolean> }) {
  const physical = usePhysical();
  const nodes = useNodes();
  const [target, setTarget] = useState("");
  const [creating, setCreating] = useState(false);
  const [deviceName, setDeviceName] = useState(node.display_name.replace(/\s+(windows|linux|cachyos)$/i, ""));
  const [partners, setPartners] = useState<string[]>([]);
  const devices = physical.data ?? [];
  const standalone = (nodes.data ?? []).filter((item) => item.node_id !== node.node_id && !item.physical_device_id);

  return (
    <section className="panel">
      <div className="panel-head"><h2>Dualboot</h2><p>Mehrere OS-Profile eines PCs als ein physisches Gerät</p></div>
      {node.physical_device_id ? (
        <>
          <p className="small">Teil von <b>{node.physical_device_name}</b> mit {siblings.length} Profilen: {siblings.map((item) => platformLabel(item)).join(", ")}.</p>
          <div className="actions mt-4">
            <button type="button" className="btn" disabled={busy} onClick={() => void run(() => api.fleet.detachProfile(node.physical_device_id!, node.node_id), "Profil vom Gerät gelöst.")}>
              <Icon name="unlink" /> Dieses Profil lösen
            </button>
          </div>
        </>
      ) : (
        <div className="stack">
          {devices.length > 0 && (
            <form className="row" onSubmit={(event) => { event.preventDefault(); if (target) void run(() => api.fleet.attachProfile(target, node.node_id), "Profil zugeordnet."); }}>
              <label className="field grow">
                <span>Einem vorhandenen Gerät zuordnen</span>
                <select className="select" value={target} onChange={(event) => setTarget(event.target.value)}>
                  <option value="">Gerät wählen</option>
                  {devices.map((device) => <option key={device.device_id} value={device.device_id}>{device.display_name}</option>)}
                </select>
              </label>
              <button type="submit" className="btn" disabled={busy || !target} style={{ alignSelf: "end" }}><Icon name="link" /> Zuordnen</button>
            </form>
          )}
          <div><button type="button" className="btn" onClick={() => setCreating(true)} disabled={standalone.length === 0} title={standalone.length ? undefined : "Kein weiteres eigenständiges Profil vorhanden"}><Icon name="plus" /> Neues physisches Gerät</button></div>
        </div>
      )}
      <Dialog
        open={creating}
        onClose={() => setCreating(false)}
        title="Physisches Gerät anlegen"
        footer={
          <>
            <button type="button" className="btn" onClick={() => setCreating(false)}>Abbrechen</button>
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy || !deviceName.trim() || partners.length === 0}
              onClick={() => void run(() => api.fleet.createPhysicalDevice(deviceName.trim(), [node.node_id, ...partners]), `„${deviceName.trim()}“ angelegt.`).then((done) => done && setCreating(false))}
            >
              Anlegen
            </button>
          </>
        }
      >
        <label className="field"><span>Name des PCs</span><input className="input" maxLength={128} value={deviceName} onChange={(event) => setDeviceName(event.target.value)} /></label>
        <fieldset className="stack-s">
          <legend className="small" style={{ fontWeight: 600 }}>Weitere OS-Profile auf diesem PC</legend>
          {standalone.map((item) => (
            <label key={item.node_id} className="switch">
              <input type="checkbox" checked={partners.includes(item.node_id)} onChange={(event) => setPartners((list) => (event.target.checked ? [...list, item.node_id] : list.filter((id) => id !== item.node_id)))} />
              {item.display_name} <span className="ink-3 small">({platformLabel(item)})</span>
            </label>
          ))}
        </fieldset>
      </Dialog>
    </section>
  );
}

function DangerZone({ node }: { node: FleetNode }) {
  const client = useQueryClient();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const remove = async () => {
    setBusy(true);
    try {
      await api.fleet.forget(node.node_id);
      client.removeQueries({ queryKey: qk.node(node.node_id) });
      await client.invalidateQueries({ queryKey: qk.nodes });
      toast.ok(`${node.display_name} wurde entfernt.`);
      navigate("geraete", { replace: true });
    } catch (error) {
      toast.fail(error);
      setBusy(false);
    }
  };
  return (
    <section className="panel danger-zone">
      <div className="panel-head"><h2>Gerät entfernen</h2></div>
      <p className="small">Entfernt das Gerät samt Telemetrie aus NCC. Der Agent verliert seinen Zugang und muss neu gekoppelt werden.</p>
      <div className="actions mt-4"><button type="button" className="btn btn-danger" onClick={() => setOpen(true)}><Icon name="trash" /> Gerät entfernen</button></div>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title={`${node.display_name} entfernen?`}
        footer={
          <>
            <button type="button" className="btn" onClick={() => setOpen(false)}>Abbrechen</button>
            <button type="button" className="btn btn-danger" disabled={busy || typed !== node.display_name} onClick={() => void remove()}>Endgültig entfernen</button>
          </>
        }
      >
        <p>Das lässt sich nicht rückgängig machen. Tippe zur Bestätigung den Namen des Geräts.</p>
        <label className="field"><span>Name: {node.display_name}</span><input className="input" value={typed} onChange={(event) => setTyped(event.target.value)} autoComplete="off" /></label>
      </Dialog>
    </section>
  );
}
