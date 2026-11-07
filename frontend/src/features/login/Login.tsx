import { useId, useState, type FormEvent } from "react";
import { describeError } from "../../api/client";
import { api } from "../../api/endpoints";
import { useAuth } from "../../app/auth";
import { Icon } from "../../components/Icon";
import { Lamp } from "../../components/ui";
import "./login.css";

type Mode = "account" | "code" | "register";

const MODES: Array<{ key: Mode; label: string }> = [
  { key: "account", label: "Konto" },
  { key: "code", label: "Admin-Code" },
  { key: "register", label: "Registrieren" },
];

export function Login({ pairing }: { pairing: string | null }) {
  const { refresh, expired, signInWithToken } = useAuth();
  const [mode, setMode] = useState<Mode>("account");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const errorId = useId();

  const finish = async () => {
    const status = await refresh();
    if (status === "anonymous") setError("Die Anmeldung wurde angenommen, aber der Browser hat keine Sitzung gespeichert. Erlaube Cookies für diese Seite und versuche es erneut.");
    if (status === "offline") setError("Server nicht erreichbar. Prüfe Tailscale oder das lokale Netz.");
  };

  const run = (action: () => Promise<unknown>) => async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await action();
      await finish();
    } catch (failure) {
      setError(describeError(failure, "Anmeldung fehlgeschlagen."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="login">
      <section className="login-hero" aria-hidden="true">
        <span className="brand-mark">no<Lamp state="go" />bz</span>
        <p className="login-claim">Command Center für die Fleet der no0bz – Gaming-PCs, Dualboot-Kisten und der Unraid-Server auf einem Stelltisch.</p>
        <TrackArt />
      </section>

      <section className="login-panel" aria-labelledby="login-title">
        <h1 id="login-title">{pairing ? "Gerät koppeln" : mode === "register" ? "Konto anlegen" : "Anmelden"}</h1>

        {pairing && (
          <p className="login-note" data-tone="shunt">
            <Icon name="link" /> Ein Gerät möchte sich mit NCC verbinden. Melde dich an – danach wird es automatisch mit deinem Zugang gekoppelt.
          </p>
        )}
        {expired && !pairing && (
          <p className="login-note" data-tone="caution">
            <Icon name="info" /> Deine Sitzung ist abgelaufen oder wurde abgemeldet. Melde dich neu an.
          </p>
        )}

        <div className="segmented login-modes" role="radiogroup" aria-label="Anmeldeart">
          {MODES.map((item) => (
            <label key={item.key}>
              <input type="radio" name="mode" value={item.key} checked={mode === item.key} onChange={() => { setMode(item.key); setError(null); }} />
              <span>{item.label}</span>
            </label>
          ))}
        </div>

        {mode === "account" && <AccountForm busy={busy} onSubmit={(username, password) => run(() => api.auth.login(username, password))} errorId={errorId} />}
        {mode === "code" && <CodeForm busy={busy} onSubmit={(code) => run(() => api.auth.redeemCode(code))} errorId={errorId} />}
        {mode === "register" && <RegisterForm busy={busy} onSubmit={(code, username, password) => run(() => api.auth.register(code, username, password))} errorId={errorId} />}

        <p id={errorId} className="form-error" role="alert" aria-live="assertive">{error}</p>

        <details className="login-legacy">
          <summary>Alte Installation mit Dashboard-Token?</summary>
          <TokenForm
            onSubmit={async (token) => {
              setBusy(true);
              setError(null);
              const status = await signInWithToken(token);
              setBusy(false);
              if (status !== "ready") setError(status === "offline" ? "Server nicht erreichbar." : "Der Token wurde nicht akzeptiert.");
            }}
            busy={busy}
          />
        </details>
      </section>
    </main>
  );
}

function AccountForm({ busy, onSubmit, errorId }: { busy: boolean; onSubmit: (username: string, password: string) => (event: FormEvent) => void; errorId: string }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  return (
    <form className="stack" onSubmit={onSubmit(username.trim().toLowerCase(), password)} aria-describedby={errorId}>
      <label className="field">
        <span>Benutzername</span>
        <input className="input" name="username" autoComplete="username" required minLength={3} maxLength={64} value={username} onChange={(event) => setUsername(event.target.value)} />
      </label>
      <label className="field">
        <span>Passwort</span>
        <input className="input" name="password" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} />
      </label>
      <button className="btn btn-primary" type="submit" disabled={busy} data-busy={busy || undefined}>Anmelden</button>
    </form>
  );
}

function CodeForm({ busy, onSubmit, errorId }: { busy: boolean; onSubmit: (code: string) => (event: FormEvent) => void; errorId: string }) {
  const [code, setCode] = useState("");
  return (
    <form className="stack" onSubmit={onSubmit(code)} aria-describedby={errorId}>
      <label className="field">
        <span>Admin-Code</span>
        <input
          className="input input-code"
          name="code"
          inputMode="text"
          autoComplete="one-time-code"
          autoCapitalize="characters"
          spellCheck={false}
          required
          pattern="[A-Z0-9]{8}"
          maxLength={8}
          placeholder="8 Zeichen"
          value={code}
          onChange={(event) => setCode(event.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ""))}
        />
        <small>Einmal-Code vom Commander, z. B. per Chat. Er gilt nur kurz und nur einmal.</small>
      </label>
      <button className="btn btn-primary" type="submit" disabled={busy || code.length !== 8}>Code einlösen</button>
    </form>
  );
}

function RegisterForm({ busy, onSubmit, errorId }: { busy: boolean; onSubmit: (code: string, username: string, password: string) => (event: FormEvent) => void; errorId: string }) {
  const [code, setCode] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const mismatch = repeat.length > 0 && password !== repeat;
  const handler = onSubmit(code.trim(), username.trim().toLowerCase(), password);
  return (
    <form
      className="stack"
      aria-describedby={errorId}
      onSubmit={(event) => {
        if (mismatch) { event.preventDefault(); return; }
        handler(event);
      }}
    >
      <label className="field">
        <span>Einladungscode</span>
        <input className="input input-code" name="invite" required minLength={8} maxLength={64} autoComplete="off" spellCheck={false} placeholder="XXXX-XXXX-XXXX" value={code} onChange={(event) => setCode(event.target.value.toUpperCase())} />
      </label>
      <label className="field">
        <span>Benutzername</span>
        <input className="input" name="username" autoComplete="username" required minLength={3} maxLength={64} pattern="[a-z0-9_.\-]+" value={username} onChange={(event) => setUsername(event.target.value.toLowerCase())} />
        <small>Kleinbuchstaben, Ziffern, Punkt, Unterstrich oder Bindestrich.</small>
      </label>
      <label className="field">
        <span>Passwort</span>
        <input className="input" name="new-password" type="password" autoComplete="new-password" required minLength={12} value={password} onChange={(event) => setPassword(event.target.value)} />
        <small>Mindestens 12 Zeichen.</small>
      </label>
      <label className="field">
        <span>Passwort wiederholen</span>
        <input className="input" name="repeat-password" type="password" autoComplete="new-password" required minLength={12} value={repeat} onChange={(event) => setRepeat(event.target.value)} aria-invalid={mismatch || undefined} />
        {mismatch && <small className="form-error">Die Passwörter sind nicht gleich.</small>}
      </label>
      <button className="btn btn-primary" type="submit" disabled={busy || mismatch}>Konto anlegen und anmelden</button>
    </form>
  );
}

function TokenForm({ busy, onSubmit }: { busy: boolean; onSubmit: (token: string) => void }) {
  const [token, setToken] = useState("");
  return (
    <form className="stack mt-4" onSubmit={(event) => { event.preventDefault(); onSubmit(token); }}>
      <label className="field">
        <span>Dashboard-Token</span>
        <input className="input" type="password" autoComplete="off" required value={token} onChange={(event) => setToken(event.target.value)} />
        <small>Wird nur im Arbeitsspeicher gehalten und beim Neuladen vergessen.</small>
      </label>
      <button className="btn" type="submit" disabled={busy || !token.trim()}>Mit Token verbinden</button>
    </form>
  );
}

/** Decorative track diagram: a main line, a turnout and three signals. */
function TrackArt() {
  return (
    <svg className="login-track" viewBox="0 0 520 180" role="presentation">
      <path d="M0 120H520" className="track" />
      <path d="M150 120C210 120 230 60 290 60H520" className="track" />
      <path d="M90 112v16M250 112v16M380 112v16M420 52v16" className="track-joint" />
      <g className="signal" transform="translate(120 92)"><rect width="14" height="22" rx="3" /><circle cx="7" cy="7" r="3.5" className="lit-go" /></g>
      <g className="signal" transform="translate(330 32)"><rect width="14" height="22" rx="3" /><circle cx="7" cy="7" r="3.5" className="lit-shunt" /></g>
      <g className="signal" transform="translate(460 92)"><rect width="14" height="22" rx="3" /><circle cx="7" cy="7" r="3.5" className="lit-caution" /></g>
      <text x="300" y="48" className="track-label">Windows</text>
      <text x="300" y="146" className="track-label">CachyOS</text>
    </svg>
  );
}
