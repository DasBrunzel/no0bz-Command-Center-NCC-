import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { api, qk } from "../../api/endpoints";
import type { TelegramSettingsUpdate } from "../../api/types";
import { useCan } from "../../app/auth";
import { Icon } from "../../components/Icon";
import { useToast } from "../../components/toast";
import { ErrorState, Lamp, Loading } from "../../components/ui";

export default function TelegramTab() {
  const can = useCan();
  const client = useQueryClient();
  const toast = useToast();
  const settings = useQuery({ queryKey: qk.telegram, queryFn: api.fleet.telegram });
  const [draft, setDraft] = useState<TelegramSettingsUpdate | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (settings.data && !draft) {
      const { configured: _configured, ...rest } = settings.data;
      setDraft(rest);
    }
  }, [settings.data, draft]);

  if (settings.isPending || !draft) return settings.isError ? <ErrorState onRetry={() => void settings.refetch()}>Die Telegram-Einstellungen konnten nicht geladen werden.</ErrorState> : <Loading />;
  const configured = settings.data!.configured;
  const locked = !can.commander || busy;

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      const saved = await api.fleet.saveTelegram(draft);
      client.setQueryData(qk.telegram, saved);
      toast.ok("Telegram-Einstellungen gespeichert.");
    } catch (error) {
      toast.fail(error);
    } finally {
      setBusy(false);
    }
  };
  const test = async () => {
    setBusy(true);
    try {
      await api.fleet.testTelegram();
      toast.ok("Testnachricht gesendet. Schau in Telegram nach.");
    } catch (error) {
      toast.fail(error, "Die Testnachricht kam nicht an.");
    } finally {
      setBusy(false);
    }
  };
  const field = (key: keyof Omit<TelegramSettingsUpdate, "enabled">, label: string, max = 128) => (
    <label className="field">
      <span>{label}</span>
      <input className="input" required maxLength={max} value={draft[key]} disabled={locked} onChange={(event) => setDraft({ ...draft, [key]: event.target.value })} />
    </label>
  );

  return (
    <form className="settings-grid" onSubmit={(event) => void save(event)}>
      <section className="panel">
        <div className="panel-head"><h2>Server-Benachrichtigungen</h2></div>
        <p className="status-label"><Lamp state={configured ? "go" : "off"} size="s" />{configured ? "Bot-Token und Chat sind auf dem Server eingerichtet." : "Auf dem Server ist kein Telegram-Bot eingerichtet (NCC_SERVER_TELEGRAM_*)."}</p>
        <label className="switch mt-4"><input type="checkbox" checked={draft.enabled} disabled={locked} onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })} /> Warnungen per Telegram senden</label>
        <div className="actions mt-4">
          <button type="button" className="btn" disabled={locked || !configured} onClick={() => void test()}><Icon name="send" /> Testnachricht senden</button>
        </div>
      </section>
      <section className="panel">
        <div className="panel-head"><h2>Texte</h2></div>
        <div className="stack">
          {field("warning_title", "Titel für Warnungen")}
          {field("critical_title", "Titel für kritische Warnungen")}
          {field("resolved_title", "Titel für Entwarnung")}
          {field("footer", "Fußzeile", 256)}
        </div>
      </section>
      <div className="actions settings-save">
        {can.commander ? <button type="submit" className="btn btn-primary" disabled={busy}>Speichern</button> : <span className="badge">nur Commander ändern Telegram</span>}
      </div>
    </form>
  );
}
