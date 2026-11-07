import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { describeError } from "../../api/client";
import { api, qk } from "../../api/endpoints";
import type { TelegramLinkCode } from "../../api/types";
import { roleLabel, useAuth, useCan } from "../../app/auth";
import { Icon } from "../../components/Icon";
import { useToast } from "../../components/toast";
import { ErrorState, Loading, Secret } from "../../components/ui";
import { fmtTime } from "../../lib/format";

export function AccountTab() {
  const { identity } = useAuth();
  const can = useCan();
  return (
    <div className="settings-grid">
      <section className="panel">
        <div className="panel-head"><h2>Angemeldet als</h2></div>
        <dl className="kv">
          <dt>Name</dt><dd>{identity?.username}</dd>
          <dt>Rolle</dt><dd>{roleLabel(can.role)}{can.beta && <span className="badge" data-tone="beta" style={{ marginInlineStart: 8 }}>nur lesen</span>}</dd>
          <dt>Sitzung</dt><dd>{identity?.personal ? "persönliches Konto" : "Admin-Code oder Dashboard-Token"}</dd>
          {can.friend && <><dt>Sichtbar</dt><dd>{identity?.fullStatistics ? "eigene Geräte, Statistik aller Geräte" : "nur eigene Geräte"}</dd></>}
        </dl>
      </section>
      <PasswordForm />
      <PersonalTelegram />
    </div>
  );
}

function PasswordForm() {
  const { identity } = useAuth();
  const toast = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mismatch = repeat.length > 0 && next !== repeat;

  if (!identity?.personal) {
    return (
      <section className="panel">
        <div className="panel-head"><h2>Passwort</h2></div>
        <p className="small ink-2">Du bist mit einem Admin-Code oder Token angemeldet. Ein Passwort gibt es nur für persönliche Konten.</p>
      </section>
    );
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (mismatch) return;
    setBusy(true);
    setError(null);
    try {
      await api.auth.changePassword(current, next);
      setCurrent(""); setNext(""); setRepeat("");
      toast.ok("Passwort geändert. Alle anderen Sitzungen sind jetzt abgemeldet.");
    } catch (failure) {
      setError(describeError(failure));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel">
      <div className="panel-head"><h2>Passwort ändern</h2></div>
      <form className="stack" onSubmit={(event) => void submit(event)}>
        <p className="notice"><Icon name="info" size={18} /> Beim Ändern werden alle anderen Sitzungen abgemeldet – auf anderen Geräten musst du dich neu anmelden. Diese Sitzung bleibt.</p>
        <input type="text" name="username" autoComplete="username" value={identity.username} readOnly hidden />
        <label className="field"><span>Aktuelles Passwort</span><input className="input" type="password" autoComplete="current-password" required value={current} onChange={(event) => setCurrent(event.target.value)} /></label>
        <label className="field"><span>Neues Passwort</span><input className="input" type="password" autoComplete="new-password" required minLength={12} value={next} onChange={(event) => setNext(event.target.value)} /><small>Mindestens 12 Zeichen.</small></label>
        <label className="field"><span>Neues Passwort wiederholen</span><input className="input" type="password" autoComplete="new-password" required minLength={12} value={repeat} onChange={(event) => setRepeat(event.target.value)} />{mismatch && <small className="form-error">Die Passwörter sind nicht gleich.</small>}</label>
        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="actions"><button type="submit" className="btn btn-primary" disabled={busy || mismatch}>Passwort ändern</button></div>
      </form>
    </section>
  );
}

function PersonalTelegram() {
  const client = useQueryClient();
  const toast = useToast();
  const [code, setCode] = useState<TelegramLinkCode | null>(null);
  // While a link code is shown, poll until the bot reports the link.
  const account = useQuery({
    queryKey: qk.myTelegram,
    queryFn: api.users.telegram,
    refetchInterval: (query) => (code && !query.state.data?.linked && new Date(code.expires_at).getTime() > Date.now() ? 5_000 : false),
  });
  const [busy, setBusy] = useState(false);

  const run = async (action: () => Promise<unknown>, success?: string) => {
    setBusy(true);
    try {
      await action();
      await client.invalidateQueries({ queryKey: qk.myTelegram });
      if (success) toast.ok(success);
    } catch (error) {
      toast.fail(error);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel">
      <div className="panel-head"><h2>Telegram für mich</h2></div>
      {account.isPending ? <Loading /> : account.isError ? (
        <ErrorState onRetry={() => void account.refetch()}>Der Telegram-Status ist nicht abrufbar.</ErrorState>
      ) : !account.data!.available ? (
        <p className="small ink-2">Persönliche Telegram-Nachrichten gibt es nur für persönliche Konten und wenn der Server einen Bot eingerichtet hat.</p>
      ) : account.data!.linked ? (
        <div className="stack">
          <p className="small">Verknüpft mit <b>{account.data!.telegram_name ?? "deinem Telegram"}</b>. Warnungen zu deinen Geräten kommen dort an.</p>
          <label className="switch"><input type="checkbox" checked={account.data!.weekly_recap} disabled={busy} onChange={(event) => void run(() => api.users.updateTelegram(event.target.checked), event.target.checked ? "Wochenrückblick an." : "Wochenrückblick aus.")} /> Wochenrückblick am Montag</label>
          <div className="actions"><button type="button" className="btn btn-danger btn-s" disabled={busy} onClick={() => void run(() => api.users.unlinkTelegram(), "Telegram-Verknüpfung gelöst.")}><Icon name="unlink" /> Verknüpfung lösen</button></div>
        </div>
      ) : (
        <div className="stack">
          <p className="small">Verknüpfe Telegram, um Warnungen zu deinen Geräten und einen Wochenrückblick zu bekommen{account.data!.bot_username ? <> vom Bot <b>@{account.data!.bot_username}</b></> : null}.</p>
          {code ? (
            <>
              <Secret value={code.code} label="Link-Code" note={<>Gilt bis {fmtTime(code.expires_at)} Uhr. Schick ihn dem Bot oder öffne den Link unten.</>} />
              {code.deep_link && <a className="btn btn-primary" href={code.deep_link} target="_blank" rel="noopener noreferrer"><Icon name="external" /> In Telegram öffnen</a>}
            </>
          ) : (
            <div className="actions"><button type="button" className="btn btn-primary" disabled={busy} onClick={() => void run(async () => setCode(await api.users.telegramLink()))}><Icon name="link" /> Telegram verknüpfen</button></div>
          )}
        </div>
      )}
    </section>
  );
}
