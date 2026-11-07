import { QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { describeError } from "../api/client";
import { api, qk } from "../api/endpoints";
import { createQueryClient } from "../api/queries";
import { ToastProvider, useToast } from "../components/toast";
import { Lamp } from "../components/ui";
import { Icon } from "../components/Icon";
import { Login } from "../features/login/Login";
import { AuthProvider, useAuth } from "./auth";
import { Shell } from "./Shell";

const queryClient = createQueryClient();

/*
 * Start the likely first view and its data while the session is checked, so
 * nothing waits in a waterfall. A 401 here is harmless: the unauthorized
 * handler ignores it until a session is running.
 */
if (!window.location.hash || window.location.hash === "#/") {
  void import("../features/overview/Overview");
  for (const [queryKey, queryFn] of [[qk.nodes, api.fleet.nodes], [qk.alerts, () => api.fleet.alerts(200)], [qk.groups, api.fleet.groups], [qk.physical, api.fleet.physicalDevices], [qk.summary, api.fleet.summary]] as const) {
    void queryClient.prefetchQuery({ queryKey, queryFn: queryFn as () => Promise<unknown>, retry: false });
  }
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthProvider>
          <Gate />
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}

/** Pairing id from a "Gerät koppeln" link, read once at start. */
const initialPairing = new URLSearchParams(window.location.search).get("pair");

function Gate() {
  const { status, refresh } = useAuth();
  const [pairing, setPairing] = useState<string | null>(initialPairing);

  if (status === "checking") return <Boot />;
  if (status === "offline") {
    return (
      <main className="boot">
        <div className="boot-card" role="alert">
          <Lamp state="stop" size="l" />
          <h1>Server nicht erreichbar</h1>
          <p>Das Dashboard findet den NCC-Server gerade nicht. Prüfe, ob Tailscale verbunden ist oder der Server auf Port 8350 läuft. Deine Anmeldung bleibt erhalten.</p>
          <button type="button" className="btn btn-primary" onClick={() => void refresh()}>
            <Icon name="refresh" /> Erneut verbinden
          </button>
        </div>
      </main>
    );
  }
  if (status === "anonymous") return <Login pairing={pairing} />;
  return (
    <>
      {pairing && <PairingApproval pairingId={pairing} onDone={() => setPairing(null)} />}
      <Shell />
    </>
  );
}

function Boot() {
  return (
    <main className="boot" aria-busy="true">
      <div className="boot-card">
        <span className="brand-mark" aria-hidden="true">no<Lamp state="go" blink />bz</span>
        <p role="status">Stellwerk fährt hoch …</p>
      </div>
    </main>
  );
}

/** After sign-in, approve the pairing request from ?pair=<id> exactly once. */
function PairingApproval({ pairingId, onDone }: { pairingId: string; onDone: () => void }) {
  const toast = useToast();
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    api.pairings
      .approve(pairingId)
      .then((pairing) => toast.ok(`„${pairing.display_name}“ ist gekoppelt. Das Gerät erscheint in wenigen Sekunden unter Geräte.`))
      .catch((error) => toast.notify(`Kopplung fehlgeschlagen: ${describeError(error)}`, "stop"))
      .finally(() => {
        const url = new URL(window.location.href);
        url.searchParams.delete("pair");
        window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
        onDone();
      });
  }, [pairingId, toast, onDone]);
  return null;
}
