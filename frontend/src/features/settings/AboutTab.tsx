import { useEffect, useState } from "react";
import { useVersion } from "../../api/queries";
import { hasLegacyToken } from "../../api/client";
import { Lamp } from "../../components/ui";

type InstallPrompt = Event & { prompt: () => Promise<void> };
let deferred: InstallPrompt | null = null;
window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  deferred = event as InstallPrompt;
});

export default function AboutTab() {
  const version = useVersion();
  const [canInstall, setCanInstall] = useState(!!deferred);
  const standalone = window.matchMedia("(display-mode: standalone)").matches;
  useEffect(() => {
    const listener = () => setCanInstall(true);
    window.addEventListener("beforeinstallprompt", listener);
    return () => window.removeEventListener("beforeinstallprompt", listener);
  }, []);
  return (
    <div className="settings-grid">
      <section className="panel">
        <div className="panel-head"><h2>no0bz Command Center</h2></div>
        <dl className="kv">
          <dt>Server</dt><dd>{version.data?.version ?? "…"}</dd>
          <dt>API</dt><dd>{version.data?.api ?? "v1"}</dd>
          <dt>Dashboard</dt><dd>2.0 „Stellwerk“</dd>
          <dt>Anmeldung</dt><dd>{hasLegacyToken() ? "Dashboard-Token (nur im Speicher)" : "Sitzungs-Cookie (HttpOnly)"}</dd>
        </dl>
      </section>
      <section className="panel">
        <div className="panel-head"><h2>Als App installieren</h2></div>
        {standalone ? (
          <p className="status-label"><Lamp state="go" size="s" />Läuft bereits als installierte App.</p>
        ) : (
          <>
            <p className="small">Installiert öffnet sich NCC in einem eigenen Fenster, das Gerüst lädt auch ohne Netz, und das Symbol zeigt die Zahl der aktiven Warnungen.</p>
            <div className="actions mt-4">
              <button type="button" className="btn btn-primary" disabled={!canInstall} onClick={() => { void deferred?.prompt(); deferred = null; setCanInstall(false); }}>App installieren</button>
            </div>
            {!canInstall && <p className="form-hint mt-4">Dein Browser bietet die Installation selbst an – in Safari über „Teilen › Zum Home-Bildschirm“, sonst über das Symbol in der Adressleiste.</p>}
          </>
        )}
      </section>
    </div>
  );
}
