import { Suspense, lazy, useEffect, useMemo, type ComponentType, type CSSProperties } from "react";
import { useAlerts, useNodes, useSummary, useVersion } from "../api/queries";
import { Icon, type IconName } from "../components/Icon";
import { ErrorState, Lamp, Loading, RelTime } from "../components/ui";
import { Link, isActive, navigate, useRoute, type Route } from "../lib/router";
import { roleLabel, useAuth, useCan, type Can } from "./auth";
import { setBadge } from "./pwa";
import { useTheme } from "./theme";

const Overview = lazy(() => import("../features/overview/Overview"));
const Fleet = lazy(() => import("../features/fleet/Fleet"));
const NodeDetail = lazy(() => import("../features/node/NodeDetail"));
const Hardware = lazy(() => import("../features/hardware/Hardware"));
const Games = lazy(() => import("../features/games/Games"));
const Chat = lazy(() => import("../features/chat/Chat"));
const Enrollment = lazy(() => import("../features/enrollment/Enrollment"));
const Releases = lazy(() => import("../features/releases/Releases"));
const Settings = lazy(() => import("../features/settings/Settings"));

interface Section {
  key: string;
  label: string;
  icon: IconName;
  visible: (can: Can) => boolean;
  mobile?: boolean;
}

const SECTIONS: Section[] = [
  { key: "", label: "Lage", icon: "overview", visible: () => true, mobile: true },
  { key: "geraete", label: "Geräte", icon: "fleet", visible: () => true, mobile: true },
  { key: "hardware", label: "Hardware", icon: "hardware", visible: () => true },
  { key: "spiele", label: "Spiele", icon: "games", visible: () => true, mobile: true },
  { key: "chat", label: "Chat", icon: "chat", visible: () => true, mobile: true },
  { key: "aufnahme", label: "Aufnahme", icon: "enroll", visible: (can) => can.team },
  { key: "releases", label: "Releases", icon: "releases", visible: (can) => can.team },
  { key: "einstellungen", label: "Einstellungen", icon: "settings", visible: () => true },
];

function View({ route }: { route: Route }) {
  const [section = "", sub] = route.path;
  const can = useCan();
  let Component: ComponentType<{ route: Route }> | null = null;
  switch (section) {
    case "": Component = Overview; break;
    case "geraete": Component = sub ? NodeDetail : Fleet; break;
    case "hardware": Component = Hardware; break;
    case "spiele": Component = Games; break;
    case "chat": Component = Chat; break;
    case "aufnahme": Component = can.team ? Enrollment : null; break;
    case "releases": Component = can.team ? Releases : null; break;
    case "einstellungen": Component = Settings; break;
  }
  if (!Component) {
    return (
      <ErrorState title="Diese Seite gibt es nicht">
        Der Link ist veraltet oder für dein Konto nicht freigegeben. <Link to="">Zur Lage</Link>
      </ErrorState>
    );
  }
  return <Component route={route} />;
}

export function Shell() {
  const route = useRoute();
  const can = useCan();
  const { identity, logout } = useAuth();
  const nodes = useNodes();
  const alerts = useAlerts();
  const summary = useSummary();
  const version = useVersion();
  const { theme, cycle } = useTheme();
  const active = useMemo(() => (alerts.data ?? []).filter((alert) => alert.active), [alerts.data]);
  const critical = active.some((alert) => alert.severity === "critical");
  const brandState = nodes.isError ? "stop" : critical ? "stop" : active.length ? "caution" : "go";
  const sections = SECTIONS.filter((section) => section.visible(can));
  const [section = ""] = route.path;

  useEffect(() => setBadge(active.length), [active.length]);
  useEffect(() => {
    const label = sections.find((item) => item.key === section)?.label ?? "NCC";
    document.title = `${active.length ? `(${active.length}) ` : ""}${label} · no0bz Command Center`;
  }, [section, active.length, sections]);

  const connection = nodes.isError
    ? { state: "stop" as const, text: "Server nicht erreichbar" }
    : nodes.isFetching && !nodes.data
      ? { state: "off" as const, text: "Verbinde …" }
      : { state: "go" as const, text: "Verbunden" };

  return (
    <div className="app">
      <a className="skip-link" href="#main" onClick={(event) => { event.preventDefault(); document.getElementById("main")?.focus(); }}>Zum Inhalt springen</a>
      <div className="rail-col">
      <nav className="rail" aria-label="Bereiche">
        <Link to="" className="brand" aria-label="no0bz Command Center – zur Lage">
          <span className="brand-mark">no<Lamp state={brandState} />bz</span>
          <span className="brand-sub">Command Center</span>
        </Link>
        <ul className="rail-nav plain" role="list">
          {sections.map((item) => (
            <li key={item.key}>
              <Link to={item.key} aria-current={isActive(route, item.key) ? "page" : undefined}>
                <Icon name={item.icon} />
                <span>{item.label}</span>
                {item.key === "" && active.length > 0 && <span className="rail-count" aria-label={`${active.length} aktive Warnungen`}>{active.length}</span>}
              </Link>
            </li>
          ))}
        </ul>
        <div className="rail-foot">
          <div className="identity">
            <Icon name="user" size={18} />
            <div>
              <strong>{identity?.username}</strong>
              {can.beta ? <span className="badge" data-tone="beta">Beta-Tester · nur lesen</span> : <span className="identity-role">{roleLabel(can.role)}</span>}
            </div>
          </div>
          <div className="rail-tools">
            <button type="button" className="btn btn-quiet btn-s" onClick={cycle} aria-label={`Darstellung: ${themeLabel(theme)}. Wechseln`} title="Darstellung wechseln">
              <Icon name={theme === "dark" ? "moon" : "sun"} /> {themeLabel(theme)}
            </button>
            <button type="button" className="btn btn-quiet btn-s" onClick={() => void logout()}>
              <Icon name="logout" /> Abmelden
            </button>
          </div>
          <p className="rail-version">Server {version.data?.version ?? "…"} · API {version.data?.api ?? "v1"}</p>
        </div>
      </nav>
      </div>

      <div className="workspace">
        <header className="bar">
          <span className="bar-connection" role="status">
            <Lamp state={connection.state} size="s" />
            <span>{connection.text}</span>
          </span>
          {summary.data && (
            <span className="bar-clock">
              Serverzeit <time dateTime={summary.data.server_time}>{new Date(summary.data.server_time).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}</time>
            </span>
          )}
          <span className="bar-spacer" />
          {can.beta && <span className="badge bar-beta" data-tone="beta">Beta-Tester</span>}
          <AlertsButton count={active.length} critical={critical} />
        </header>
        <main id="main" className="content" tabIndex={-1}>
          <Suspense fallback={<Loading label="Bereich wird geladen" />}>
            <View route={route} />
          </Suspense>
        </main>
      </div>

      <MobileBar sections={sections} route={route} alertCount={active.length} onLogout={() => void logout()} />
    </div>
  );
}

function themeLabel(theme: string): string {
  return theme === "dark" ? "Nachtschicht" : theme === "light" ? "Emaille" : "Automatisch";
}

function AlertsButton({ count, critical }: { count: number; critical: boolean }) {
  const alerts = useAlerts();
  const active = (alerts.data ?? []).filter((alert) => alert.active);
  return (
    <>
      <button
        type="button"
        className="btn btn-s bar-alerts"
        popoverTarget="alerts-popover"
        data-count={count || undefined}
        style={{ anchorName: "--alerts" } as CSSProperties}
        aria-label={count ? `${count} aktive Warnungen anzeigen` : "Keine aktiven Warnungen"}
      >
        <Lamp state={count ? (critical ? "stop" : "caution") : "off"} size="s" blink={critical} />
        <span>{count ? `${count} ${count === 1 ? "Warnung" : "Warnungen"}` : "Keine Warnungen"}</span>
      </button>
      <div id="alerts-popover" popover="auto" className="menu alerts-menu" data-anchored="end" style={{ positionAnchor: "--alerts" } as CSSProperties}>
        {active.length === 0 ? (
          <p className="alerts-empty">Alles im grünen Bereich. Kein Gerät meldet gerade etwas.</p>
        ) : (
          <ul className="plain" role="list">
            {active.map((alert) => (
              <li key={alert.alert_id}>
                <a
                  className="menu-item"
                  href={`#/geraete/${encodeURIComponent(alert.node_id)}`}
                  onClick={(event) => {
                    event.preventDefault();
                    (document.getElementById("alerts-popover") as HTMLElement | null)?.hidePopover();
                    navigate(`geraete/${encodeURIComponent(alert.node_id)}`);
                  }}
                >
                  <Lamp state={alert.severity === "critical" ? "stop" : "caution"} size="s" />
                  <span>
                    <b>{alert.display_name}</b>
                    <br />
                    <small>{alert.message} · <RelTime iso={alert.opened_at} /></small>
                  </span>
                </a>
              </li>
            ))}
          </ul>
        )}
        <hr />
        <a className="menu-item" href="#/" onClick={(event) => { event.preventDefault(); (document.getElementById("alerts-popover") as HTMLElement | null)?.hidePopover(); navigate(""); }}>Zum Störmelder</a>
      </div>
    </>
  );
}

function MobileBar({ sections, route, alertCount, onLogout }: { sections: Section[]; route: Route; alertCount: number; onLogout: () => void }) {
  const primary = sections.filter((item) => item.mobile);
  const rest = sections.filter((item) => !item.mobile);
  return (
    <nav className="tabbar" aria-label="Bereiche (mobil)">
      {primary.map((item) => (
        <Link key={item.key} to={item.key} aria-current={isActive(route, item.key) ? "page" : undefined}>
          <Icon name={item.icon} />
          <span>{item.label}</span>
          {item.key === "" && alertCount > 0 && <span className="rail-count">{alertCount}</span>}
        </Link>
      ))}
      <button type="button" popoverTarget="more-popover" aria-current={rest.some((item) => isActive(route, item.key)) ? "page" : undefined} style={{ anchorName: "--more" } as CSSProperties}>
        <Icon name="more" />
        <span>Mehr</span>
      </button>
      <div id="more-popover" popover="auto" className="menu more-menu">
        {rest.map((item) => (
          <a
            key={item.key}
            className="menu-item"
            href={`#/${item.key}`}
            onClick={(event) => { event.preventDefault(); (event.currentTarget.closest("[popover]") as HTMLElement).hidePopover(); navigate(item.key); }}
          >
            <Icon name={item.icon} /> {item.label}
          </a>
        ))}
        <hr />
        <button type="button" className="menu-item" onClick={onLogout}><Icon name="logout" /> Abmelden</button>
      </div>
    </nav>
  );
}
