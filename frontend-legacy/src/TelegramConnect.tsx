import React, { useCallback, useEffect, useState } from "react";
import { Send } from "lucide-react";

type TelegramAccount = { available: boolean; linked: boolean; telegram_name: string | null; weekly_recap: boolean; bot_username: string | null };
type LinkCode = { code: string; expires_at: string; deep_link: string | null };

const authHeaders = (token: string): Record<string, string> => (token ? { "X-NCC-Dashboard-Token": token } : {});

/** Lets every account receive its own alerts and the weekly recap by Telegram. */
export function TelegramConnect({ token, isFriend, hasAccount }: { token: string; isFriend: boolean; hasAccount: boolean }) {
  const [account, setAccount] = useState<TelegramAccount | null>(null);
  const [code, setCode] = useState<LinkCode | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const request = useCallback(async (method: string, path: string, body?: unknown) => {
    const response = await fetch(`/api/v1/users/me/telegram${path}`, {
      method, headers: { ...authHeaders(token), "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!response.ok) throw new Error(String(response.status));
    return response.status === 204 ? null : response.json();
  }, [token]);
  const refresh = useCallback(async () => {
    try { setAccount(await request("GET", "")); } catch { setAccount(null); }
  }, [request]);
  useEffect(() => { void refresh(); }, [refresh]);
  // While a code is open, notice when the bot linked the chat.
  useEffect(() => {
    if (!code || account?.linked) return;
    const timer = window.setInterval(() => void refresh(), 4000);
    return () => window.clearInterval(timer);
  }, [code, account?.linked, refresh]);
  useEffect(() => { if (account?.linked) setCode(null); }, [account?.linked]);

  const act = async (work: () => Promise<unknown>) => {
    setBusy(true); setError("");
    try { await work(); await refresh(); }
    catch { setError("Das hat nicht geklappt. Versuch es gleich noch einmal."); }
    finally { setBusy(false); }
  };
  if (!hasAccount || !account) return null;
  return <section className="surface settings-card telegram-connect-card">
    <header className="section-head"><div><span className="eyebrow">BENACHRICHTIGUNGEN</span><h2>Telegram verbinden</h2></div><Send size={19} /></header>
    {!account.available && <p>Telegram ist auf diesem NCC-Server noch nicht eingerichtet.</p>}
    {account.available && !account.linked && <>
      <p>{isFriend ? "Bekomme Warnungen deiner Geräte und montags einen Wochenrückblick direkt aufs Handy." : "Verbinde dein persönliches Telegram mit diesem Konto. Warnungen und der Wochenrückblick kommen dann zusätzlich dorthin."}</p>
      {!code && <button type="button" className="primary" disabled={busy} onClick={() => void act(async () => setCode(await request("POST", "/link")))}>Verbindungscode erzeugen</button>}
      {code && <div className="telegram-code">
        {code.deep_link && <a className="primary" href={code.deep_link} target="_blank" rel="noreferrer">In Telegram öffnen</a>}
        <span>oder schick dem Bot{account.bot_username ? <> <b>@{account.bot_username}</b></> : null} diesen Code:</span>
        <code>{code.code}</code>
        <small>Gültig bis {new Date(code.expires_at).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })} Uhr. Diese Seite merkt automatisch, wenn die Verbindung steht.</small>
      </div>}
    </>}
    {account.available && account.linked && <>
      <p>Verbunden{account.telegram_name ? <> mit <b>{account.telegram_name}</b></> : null}. {isFriend ? "Du bekommst die Warnungen deiner Geräte." : "Du bekommst die Warnungen aller Geräte."}</p>
      <label className="toggle-line"><span><b>Wochenrückblick</b><small>Jeden Montag um 9 Uhr: Spielzeit, Top-Spiel, Höchsttemperaturen</small></span>
        <input type="checkbox" checked={account.weekly_recap} disabled={busy} onChange={(event) => void act(() => request("PATCH", "", { weekly_recap: event.target.checked }))} /></label>
      <button type="button" className="outline-button" disabled={busy} onClick={() => void act(() => request("DELETE", ""))}>Verbindung trennen</button>
    </>}
    {error && <small className="form-error">{error}</small>}
  </section>;
}
