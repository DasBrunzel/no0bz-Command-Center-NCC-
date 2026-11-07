import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { POLL, api, qk } from "../../api/endpoints";
import type { AdminCodeCreated, AgentInvitation, AgentInvitationCreated, AgentPairing } from "../../api/types";
import { roleLabel, useCan } from "../../app/auth";
import { Icon } from "../../components/Icon";
import { useToast } from "../../components/toast";
import { ConfirmDialog, CopyButton, Empty, ErrorState, Lamp, Loading, PageHead, RelTime, Secret, useNow } from "../../components/ui";
import { fmtDateTime } from "../../lib/format";
import type { LampState } from "../../lib/node";
import type { Route } from "../../lib/router";
import "./enrollment.css";

const PAIRING_STATE: Record<AgentPairing["status"], { text: string; lamp: LampState }> = {
  waiting: { text: "Wartet auf Freigabe", lamp: "caution" },
  approved: { text: "Freigegeben", lamp: "shunt" },
  claimed: { text: "Verbunden", lamp: "go" },
  expired: { text: "Abgelaufen", lamp: "off" },
  cancelled: { text: "Abgebrochen", lamp: "off" },
};

export default function Enrollment(_: { route: Route }) {
  return (
    <div className="enrollment">
      <PageHead title="Geräte aufnehmen" lead="Neue PCs koppeln, Agenten einladen und Einmal-Codes für Freunde ausstellen." />
      <div className="enroll-grid">
        <Pairings />
        <Install />
      </div>
      <Invitations />
      <AdminCodes />
    </div>
  );
}

/* ── Pairing requests ─────────────────────────────────────────────── */

function Pairings() {
  const can = useCan();
  const client = useQueryClient();
  const toast = useToast();
  const now = useNow();
  const pairings = useQuery({ queryKey: qk.pairings, queryFn: api.pairings.list, refetchInterval: POLL.pairings });
  const [busy, setBusy] = useState<string | null>(null);
  const list = pairings.data ?? [];
  const open = list.filter((item) => item.status === "waiting" || item.status === "approved");
  const done = list.filter((item) => item.status !== "waiting" && item.status !== "approved").slice(0, 8);

  const approve = async (pairing: AgentPairing) => {
    setBusy(pairing.pairing_id);
    try {
      await api.pairings.approve(pairing.pairing_id);
      await client.invalidateQueries({ queryKey: qk.pairings });
      toast.ok(`${pairing.display_name} freigegeben. Der Agent holt sich jetzt seinen Zugang.`);
    } catch (error) {
      toast.fail(error);
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="panel" aria-labelledby="pairings-title">
      <div className="panel-head">
        <h2 id="pairings-title">Kopplungsanfragen</h2>
        <p>alle 5 Sekunden aktualisiert</p>
      </div>
      {pairings.isPending ? <Loading /> : pairings.isError && !pairings.data ? (
        <ErrorState onRetry={() => void pairings.refetch()}>Die Kopplungsanfragen konnten nicht geladen werden.</ErrorState>
      ) : open.length === 0 ? (
        <Empty title="Keine offene Anfrage" icon="link">
          Öffne am neuen PC im NCC-Symbol im Infobereich „Gerät koppeln…“. Der Link führt hierher und koppelt das Gerät nach der Anmeldung automatisch.
        </Empty>
      ) : (
        <ul className="plain pairing-list" role="list">
          {open.map((pairing) => {
            const state = PAIRING_STATE[pairing.status];
            const left = Math.max(0, Math.round((new Date(pairing.expires_at).getTime() - now) / 60000));
            return (
              <li key={pairing.pairing_id} data-status={pairing.status}>
                <Lamp state={state.lamp} blink={pairing.status === "waiting"} />
                <div className="grow">
                  <b>{pairing.display_name}</b>
                  <small>{pairing.platform} · {state.text} · läuft in {left} min ab</small>
                </div>
                {pairing.status === "waiting" && can.commander && (
                  <button type="button" className="btn btn-primary btn-s" disabled={busy === pairing.pairing_id} onClick={() => void approve(pairing)}>Freigeben</button>
                )}
                {pairing.status === "waiting" && !can.commander && <span className="badge">Commander gibt frei</span>}
              </li>
            );
          })}
        </ul>
      )}
      {done.length > 0 && (
        <details className="mt-4 small">
          <summary className="ink-3" style={{ cursor: "pointer" }}>Erledigt ({done.length})</summary>
          <ul className="plain pairing-list pairing-done" role="list">
            {done.map((pairing) => (
              <li key={pairing.pairing_id}>
                <Lamp state={PAIRING_STATE[pairing.status].lamp} size="s" />
                <span className="grow">{pairing.display_name} <span className="ink-3">· {PAIRING_STATE[pairing.status].text}</span></span>
                <span className="ink-3"><RelTime iso={pairing.created_at} /></span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

/* ── Install command ──────────────────────────────────────────────── */

function Install() {
  const [platform, setPlatform] = useState<"windows" | "linux">("windows");
  const server = window.location.hostname;
  const command = platform === "linux"
    ? `cd ~/ncc && sudo ./scripts/install_ncc_agent_service.sh --tailscale ${server}`
    : `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\install_ncc_service.ps1 -Component Agent -Tailscale -ServerUrl ${server}`;
  return (
    <section className="panel" aria-labelledby="install-title">
      <div className="panel-head"><h2 id="install-title">Agent installieren</h2></div>
      <div className="segmented" role="radiogroup" aria-label="Betriebssystem">
        <label><input type="radio" name="os" checked={platform === "windows"} onChange={() => setPlatform("windows")} /><span>Windows</span></label>
        <label><input type="radio" name="os" checked={platform === "linux"} onChange={() => setPlatform("linux")} /><span>Linux / CachyOS</span></label>
      </div>
      <ol className="steps">
        <li>NCC-Paket auf den PC holen und im Ordner ein {platform === "windows" ? "PowerShell-Fenster als Administrator" : "Terminal"} öffnen.</li>
        <li>
          Diesen Befehl ausführen:
          <pre className="command"><code>{command}</code></pre>
          <CopyButton value={command} label="Befehl kopieren" />
        </li>
        <li>Der Agent startet und zeigt einen Kopplungslink. Öffnen, anmelden, fertig – die Anfrage erscheint links.</li>
      </ol>
    </section>
  );
}

/* ── Agent invitations (tokens) ───────────────────────────────────── */

const INVITE_STATE: Record<AgentInvitation["status"], { text: string; tone?: "go" | "caution" | "stop" }> = {
  ready: { text: "Bereit", tone: "caution" },
  bound: { text: "Verbunden", tone: "go" },
  expired: { text: "Abgelaufen" },
  revoked: { text: "Widerrufen", tone: "stop" },
};

function Invitations() {
  const can = useCan();
  const client = useQueryClient();
  const toast = useToast();
  const invitations = useQuery({ queryKey: qk.invitations, queryFn: api.invitations.list, refetchInterval: POLL.admin });
  const [name, setName] = useState("");
  const [hours, setHours] = useState(168);
  const [created, setCreated] = useState<AgentInvitationCreated | null>(null);
  const [revoke, setRevoke] = useState<AgentInvitation | null>(null);
  const [busy, setBusy] = useState(false);

  const create = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await api.invitations.create(name.trim(), hours);
      setCreated(result);
      setName("");
      await client.invalidateQueries({ queryKey: qk.invitations });
    } catch (error) {
      toast.fail(error);
    } finally {
      setBusy(false);
    }
  };
  const act = async (action: () => Promise<unknown>, success: string) => {
    setBusy(true);
    try {
      await action();
      await client.invalidateQueries({ queryKey: qk.invitations });
      toast.ok(success);
    } catch (error) {
      toast.fail(error);
    } finally {
      setBusy(false);
      setRevoke(null);
    }
  };

  return (
    <section className="panel section" aria-labelledby="invites-title">
      <div className="panel-head">
        <h2 id="invites-title">Agent-Einladungen</h2>
        <p>Token für Agenten, die ohne Kopplungslink eingerichtet werden</p>
      </div>
      {can.commander ? (
        <form className="row" onSubmit={(event) => void create(event)}>
          <label className="field grow"><span>Für welches Gerät?</span><input className="input" required maxLength={128} value={name} onChange={(event) => setName(event.target.value)} placeholder="z. B. Jonas-PC" /></label>
          <label className="field"><span>Gültig</span>
            <select className="select" value={hours} onChange={(event) => setHours(Number(event.target.value))}>
              <option value={24}>1 Tag</option><option value={168}>7 Tage</option><option value={720}>30 Tage</option><option value={0}>unbegrenzt</option>
            </select>
          </label>
          <button type="submit" className="btn btn-primary" disabled={busy || !name.trim()} style={{ alignSelf: "end" }}><Icon name="plus" /> Einladung erstellen</button>
        </form>
      ) : (
        <p className="form-hint">Einladungen erstellen und widerrufen dürfen Commander.</p>
      )}
      {created && (
        <div className="mt-4">
          <Secret value={created.token} label={`Agent-Token für ${created.name}`} long note="Trage ihn in die ncc-agent.env des Geräts ein. Der Server speichert nur einen Prüfwert – nach dem Schließen ist der Token nicht mehr abrufbar." />
          <button type="button" className="btn btn-s mt-4" onClick={() => setCreated(null)}>Gespeichert, ausblenden</button>
        </div>
      )}
      {invitations.isPending ? <Loading /> : invitations.isError && !invitations.data ? (
        <ErrorState onRetry={() => void invitations.refetch()}>Die Einladungen konnten nicht geladen werden.</ErrorState>
      ) : !invitations.data?.length ? (
        <p className="ink-3 small mt-4">Noch keine Einladungen.</p>
      ) : (
        <div className="table-wrap mt-4">
          <table className="table">
            <thead><tr><th>Name</th><th>Status</th><th>Gerät</th><th>Läuft ab</th><th>Zuletzt genutzt</th>{can.commander && <th className="r"><span className="visually-hidden">Aktionen</span></th>}</tr></thead>
            <tbody>
              {invitations.data.map((item) => (
                <tr key={item.token_id}>
                  <td>{item.name}</td>
                  <td><span className="badge" data-tone={INVITE_STATE[item.status].tone}>{INVITE_STATE[item.status].text}</span></td>
                  <td>{item.node_name ?? <span className="ink-3">–</span>}</td>
                  <td>{item.expires_at ? fmtDateTime(item.expires_at) : "nie"}</td>
                  <td>{item.last_used_at ? <RelTime iso={item.last_used_at} /> : <span className="ink-3">nie</span>}</td>
                  {can.commander && (
                    <td className="r">
                      {item.status === "revoked" ? (
                        <button type="button" className="btn btn-quiet btn-s" disabled={busy} onClick={() => void act(() => api.invitations.remove(item.token_id), "Einladung entfernt.")}><Icon name="trash" /> Entfernen</button>
                      ) : (
                        <button type="button" className="btn btn-danger btn-s" disabled={busy} onClick={() => setRevoke(item)}>Widerrufen</button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <ConfirmDialog
        open={!!revoke}
        onClose={() => setRevoke(null)}
        danger
        title={`Einladung „${revoke?.name}“ widerrufen?`}
        confirmLabel="Widerrufen"
        busy={busy}
        onConfirm={() => revoke && void act(() => api.invitations.revoke(revoke.token_id), "Einladung widerrufen.")}
      >
        <p>{revoke?.status === "bound" ? `Der Agent auf ${revoke.node_name ?? "dem Gerät"} verliert sofort seinen Zugang und muss neu gekoppelt werden.` : "Der Token kann danach nicht mehr verwendet werden."}</p>
      </ConfirmDialog>
    </section>
  );
}

/* ── Admin codes ──────────────────────────────────────────────────── */

const CODE_STATE = { ready: { text: "Gültig", tone: "caution" }, used: { text: "Eingelöst", tone: "go" }, expired: { text: "Abgelaufen", tone: undefined }, revoked: { text: "Widerrufen", tone: "stop" } } as const;

function AdminCodes() {
  const can = useCan();
  const client = useQueryClient();
  const toast = useToast();
  const codes = useQuery({ queryKey: qk.adminCodes, queryFn: api.adminCodes.list, refetchInterval: POLL.admin });
  const [label, setLabel] = useState("");
  const [minutes, setMinutes] = useState(15);
  const [beta, setBeta] = useState(true);
  const [created, setCreated] = useState<(AdminCodeCreated & { label: string }) | null>(null);
  const [busy, setBusy] = useState(false);

  const create = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await api.adminCodes.create(label.trim(), minutes, beta);
      setCreated({ ...result, label: label.trim() });
      setLabel("");
      await client.invalidateQueries({ queryKey: qk.adminCodes });
    } catch (error) {
      toast.fail(error);
    } finally {
      setBusy(false);
    }
  };
  const revoke = async (codeId: string) => {
    setBusy(true);
    try {
      await api.adminCodes.revoke(codeId);
      await client.invalidateQueries({ queryKey: qk.adminCodes });
      toast.ok("Code widerrufen. Sitzungen, die damit angemeldet sind, enden sofort.");
    } catch (error) {
      toast.fail(error);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel section" aria-labelledby="codes-title">
      <div className="panel-head">
        <h2 id="codes-title">Admin-Codes</h2>
        <p>Einmal-Codes mit 8 Zeichen für eine schnelle Anmeldung ohne Konto</p>
      </div>
      {can.commander ? (
        <form className="row" onSubmit={(event) => void create(event)}>
          <label className="field grow"><span>Wofür?</span><input className="input" required maxLength={128} value={label} onChange={(event) => setLabel(event.target.value)} placeholder="z. B. Kalles Handy" /></label>
          <label className="field"><span>Gültig</span>
            <select className="select" value={minutes} onChange={(event) => setMinutes(Number(event.target.value))}>
              <option value={5}>5 Minuten</option><option value={15}>15 Minuten</option><option value={30}>30 Minuten</option><option value={60}>60 Minuten</option>
            </select>
          </label>
          <label className="switch" style={{ alignSelf: "end", minBlockSize: "2.5rem" }}><input type="checkbox" checked={beta} onChange={(event) => setBeta(event.target.checked)} /> Als Beta-Tester (nur lesen)</label>
          <button type="submit" className="btn btn-primary" disabled={busy || !label.trim()} style={{ alignSelf: "end" }}><Icon name="plus" /> Code erstellen</button>
        </form>
      ) : (
        <p className="form-hint">Codes erstellen und widerrufen dürfen Commander.</p>
      )}
      {created && (
        <div className="mt-4">
          <Secret value={created.code} label={`${roleLabel(created.access_role)}-Code für ${created.label}`} note={<>Gilt einmal und bis {fmtDateTime(created.expires_at)}. Schick ihn direkt weiter – nach dem Ausblenden ist er weg.</>} />
          <button type="button" className="btn btn-s mt-4" onClick={() => setCreated(null)}>Weitergegeben, ausblenden</button>
        </div>
      )}
      {codes.isPending ? <Loading /> : codes.isError && !codes.data ? (
        <ErrorState onRetry={() => void codes.refetch()}>Die Codes konnten nicht geladen werden.</ErrorState>
      ) : !codes.data?.length ? (
        <p className="ink-3 small mt-4">Noch keine Codes erstellt.</p>
      ) : (
        <div className="table-wrap mt-4">
          <table className="table">
            <thead><tr><th>Wofür</th><th>Rolle</th><th>Status</th><th>Erstellt</th><th>Läuft ab</th>{can.commander && <th className="r"><span className="visually-hidden">Aktionen</span></th>}</tr></thead>
            <tbody>
              {codes.data.map((code) => (
                <tr key={code.code_id}>
                  <td>{code.label}</td>
                  <td>{roleLabel(code.access_role)}</td>
                  <td><span className="badge" data-tone={CODE_STATE[code.status].tone}>{CODE_STATE[code.status].text}</span></td>
                  <td><RelTime iso={code.created_at} /></td>
                  <td>{fmtDateTime(code.expires_at)}</td>
                  {can.commander && (
                    <td className="r">
                      {(code.status === "ready" || code.status === "used") && (
                        <button type="button" className="btn btn-danger btn-s" disabled={busy} onClick={() => void revoke(code.code_id)} title={code.status === "used" ? "Beendet auch die Sitzung, die mit diesem Code angemeldet ist" : undefined}>Widerrufen</button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
