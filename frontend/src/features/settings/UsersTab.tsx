import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { POLL, api, qk } from "../../api/endpoints";
import type { AccountInvite, AccountInviteCreated, DashboardRole, DashboardUser } from "../../api/types";
import { roleLabel, useAuth } from "../../app/auth";
import { Icon } from "../../components/Icon";
import { useToast } from "../../components/toast";
import { ConfirmDialog, Dialog, ErrorState, Loading, RelTime, Secret } from "../../components/ui";
import { fmtDateTime } from "../../lib/format";

const ROLES: DashboardRole[] = ["commander", "beta_tester", "friend"];
const ROLE_HINT: Record<DashboardRole, string> = {
  commander: "darf alles",
  beta_tester: "sieht alles, ändert nichts",
  friend: "sieht und verwaltet nur eigene Geräte",
};

export default function UsersTab() {
  const { identity } = useAuth();
  const client = useQueryClient();
  const toast = useToast();
  const users = useQuery({ queryKey: qk.users, queryFn: api.users.list, refetchInterval: POLL.admin });
  const [creating, setCreating] = useState(false);
  const [deactivate, setDeactivate] = useState<DashboardUser | null>(null);
  const [busy, setBusy] = useState(false);

  const update = async (user: DashboardUser, patch: Parameters<typeof api.users.update>[1], success: string) => {
    if (!user.user_id) return;
    setBusy(true);
    try {
      await api.users.update(user.user_id, patch);
      await client.invalidateQueries({ queryKey: qk.users });
      toast.ok(success);
    } catch (error) {
      toast.fail(error);
    } finally {
      setBusy(false);
      setDeactivate(null);
    }
  };

  return (
    <div className="stack">
      <section className="panel">
        <div className="panel-head">
          <h2>Konten</h2>
          <button type="button" className="btn btn-primary btn-s" onClick={() => setCreating(true)}><Icon name="plus" /> Konto anlegen</button>
        </div>
        {users.isPending ? <Loading /> : users.isError && !users.data ? (
          <ErrorState onRetry={() => void users.refetch()}>Die Konten konnten nicht geladen werden.</ErrorState>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Name</th><th>Rolle</th><th>Status</th><th className="r">Geräte</th><th>Statistik</th><th>Seit</th><th className="r"><span className="visually-hidden">Aktionen</span></th></tr></thead>
              <tbody>
                {(users.data ?? []).map((user) => {
                  const self = user.user_id === identity?.userId;
                  return (
                    <tr key={user.user_id ?? user.username} data-inactive={!user.active || undefined}>
                      <td><b>{user.username}</b>{self && <span className="badge" style={{ marginInlineStart: 8 }}>du</span>}</td>
                      <td>
                        <label className="visually-hidden" htmlFor={`role-${user.user_id}`}>Rolle von {user.username}</label>
                        <select id={`role-${user.user_id}`} className="select select-s" value={user.role} disabled={busy || !user.active} onChange={(event) => void update(user, { role: event.target.value as DashboardRole }, `${user.username} ist jetzt ${roleLabel(event.target.value as DashboardRole)}.`)}>
                          {ROLES.map((role) => <option key={role} value={role}>{roleLabel(role)}</option>)}
                        </select>
                      </td>
                      <td><span className="badge" data-tone={user.active ? "go" : undefined}>{user.active ? "aktiv" : "deaktiviert"}</span></td>
                      <td className="r">{user.device_count}</td>
                      <td>
                        {user.role === "friend" ? (
                          <label className="switch small"><input type="checkbox" checked={user.full_statistics} disabled={busy} onChange={(event) => void update(user, { full_statistics: event.target.checked }, event.target.checked ? `${user.username} sieht jetzt die Statistik aller Geräte.` : `${user.username} sieht nur noch eigene Statistik.`)} /> alle Geräte</label>
                        ) : <span className="ink-3 small">alle Geräte</span>}
                      </td>
                      <td>{user.created_at ? <RelTime iso={user.created_at} /> : "–"}</td>
                      <td className="r">
                        {user.active ? (
                          <button type="button" className="btn btn-danger btn-s" disabled={busy || self} title={self ? "Das eigene Konto lässt sich nicht deaktivieren." : undefined} onClick={() => setDeactivate(user)}>Deaktivieren</button>
                        ) : (
                          <button type="button" className="btn btn-s" disabled={busy} onClick={() => void update(user, { active: true }, `${user.username} ist wieder aktiv.`)}>Aktivieren</button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <p className="form-hint mt-4">{ROLES.map((role) => `${roleLabel(role)}: ${ROLE_HINT[role]}`).join(" · ")}</p>
      </section>

      <Invites />

      {creating && <CreateUser onClose={() => setCreating(false)} />}
      <ConfirmDialog
        open={!!deactivate}
        onClose={() => setDeactivate(null)}
        danger
        title={`${deactivate?.username} deaktivieren?`}
        confirmLabel="Deaktivieren"
        busy={busy}
        onConfirm={() => deactivate && void update(deactivate, { active: false }, `${deactivate.username} ist deaktiviert und abgemeldet.`)}
      >
        <p>Das Konto kann sich nicht mehr anmelden, laufende Sitzungen enden sofort. Du kannst es später wieder aktivieren.</p>
      </ConfirmDialog>
    </div>
  );
}

function CreateUser({ onClose }: { onClose: () => void }) {
  const client = useQueryClient();
  const toast = useToast();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<DashboardRole>("beta_tester");
  const [busy, setBusy] = useState(false);
  const submit = async (event?: FormEvent) => {
    event?.preventDefault();
    setBusy(true);
    try {
      await api.users.create(username.trim().toLowerCase(), password, role);
      await client.invalidateQueries({ queryKey: qk.users });
      toast.ok(`Konto ${username.trim().toLowerCase()} angelegt.`);
      onClose();
    } catch (error) {
      toast.fail(error);
    } finally {
      setBusy(false);
    }
  };
  const valid = /^[a-z0-9_.-]{3,64}$/.test(username.trim().toLowerCase()) && password.length >= 12;
  return (
    <Dialog open onClose={onClose} title="Konto anlegen" footer={<><button type="button" className="btn" onClick={onClose}>Abbrechen</button><button type="submit" form="create-user" className="btn btn-primary" disabled={busy || !valid}>Anlegen</button></>}>
      <form id="create-user" className="stack" onSubmit={(event) => void submit(event)}>
        <label className="field"><span>Benutzername</span><input className="input" required pattern="[a-z0-9_.\-]{3,64}" autoComplete="off" value={username} onChange={(event) => setUsername(event.target.value.toLowerCase())} /><small>Kleinbuchstaben, Ziffern, Punkt, Unterstrich, Bindestrich.</small></label>
        <label className="field"><span>Startpasswort</span><input className="input" type="password" required minLength={12} autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} /><small>Mindestens 12 Zeichen. Gib es sicher weiter; die Person kann es selbst ändern.</small></label>
        <label className="field"><span>Rolle</span>
          <select className="select" value={role} onChange={(event) => setRole(event.target.value as DashboardRole)}>
            {ROLES.map((item) => <option key={item} value={item}>{roleLabel(item)} – {ROLE_HINT[item]}</option>)}
          </select>
        </label>
      </form>
    </Dialog>
  );
}

const INVITE_STATE: Record<AccountInvite["status"], { text: string; tone?: "go" | "caution" | "stop" }> = {
  open: { text: "offen", tone: "caution" }, used: { text: "eingelöst", tone: "go" }, expired: { text: "abgelaufen" }, revoked: { text: "widerrufen", tone: "stop" },
};

function Invites() {
  const client = useQueryClient();
  const toast = useToast();
  const invites = useQuery({ queryKey: qk.invites, queryFn: api.users.invites, refetchInterval: POLL.admin });
  const [label, setLabel] = useState("");
  const [days, setDays] = useState(7);
  const [created, setCreated] = useState<AccountInviteCreated | null>(null);
  const [busy, setBusy] = useState(false);

  const create = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      setCreated(await api.users.createInvite(label.trim(), days));
      setLabel("");
      await client.invalidateQueries({ queryKey: qk.invites });
    } catch (error) {
      toast.fail(error);
    } finally {
      setBusy(false);
    }
  };
  const revoke = async (invite: AccountInvite) => {
    setBusy(true);
    try {
      await api.users.revokeInvite(invite.invite_id);
      await client.invalidateQueries({ queryKey: qk.invites });
      toast.ok(`Einladung „${invite.label}“ widerrufen.`);
    } catch (error) {
      toast.fail(error);
    } finally {
      setBusy(false);
    }
  };
  const registerLink = `${window.location.origin}/`;

  return (
    <section className="panel">
      <div className="panel-head"><h2>Konto-Einladungen</h2><p>Freunde registrieren sich damit selbst</p></div>
      <form className="row" onSubmit={(event) => void create(event)}>
        <label className="field grow"><span>Für wen?</span><input className="input" required maxLength={128} value={label} onChange={(event) => setLabel(event.target.value)} placeholder="z. B. Jonas" /></label>
        <label className="field"><span>Gültig</span>
          <select className="select" value={days} onChange={(event) => setDays(Number(event.target.value))}>
            <option value={1}>1 Tag</option><option value={7}>7 Tage</option><option value={14}>14 Tage</option><option value={30}>30 Tage</option>
          </select>
        </label>
        <button type="submit" className="btn btn-primary" disabled={busy || !label.trim()} style={{ alignSelf: "end" }}><Icon name="plus" /> Einladung erstellen</button>
      </form>
      {created && (
        <div className="mt-4">
          <Secret value={created.code} label={`Einladungscode für ${created.label}`} note={<>Gilt bis {fmtDateTime(created.expires_at)}. {created.label} öffnet {registerLink}, wählt „Registrieren“ und gibt den Code ein. Der Server kennt nur einen Prüfwert.</>} />
          <button type="button" className="btn btn-s mt-4" onClick={() => setCreated(null)}>Weitergegeben, ausblenden</button>
        </div>
      )}
      {invites.isPending ? <Loading /> : invites.isError && !invites.data ? (
        <ErrorState onRetry={() => void invites.refetch()}>Die Einladungen konnten nicht geladen werden.</ErrorState>
      ) : !invites.data?.length ? (
        <p className="ink-3 small mt-4">Noch keine Einladungen.</p>
      ) : (
        <div className="table-wrap mt-4">
          <table className="table">
            <thead><tr><th>Für</th><th>Status</th><th>Eingelöst von</th><th>Läuft ab</th><th className="r"><span className="visually-hidden">Aktionen</span></th></tr></thead>
            <tbody>
              {invites.data.map((invite) => (
                <tr key={invite.invite_id}>
                  <td>{invite.label}</td>
                  <td><span className="badge" data-tone={INVITE_STATE[invite.status].tone}>{INVITE_STATE[invite.status].text}</span></td>
                  <td>{invite.used_by ?? <span className="ink-3">–</span>}</td>
                  <td>{fmtDateTime(invite.expires_at)}</td>
                  <td className="r">{invite.status === "open" && <button type="button" className="btn btn-danger btn-s" disabled={busy} onClick={() => void revoke(invite)}>Widerrufen</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
