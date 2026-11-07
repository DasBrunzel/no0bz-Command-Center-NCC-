import { lazy, Suspense, type CSSProperties } from "react";
import { ApiError } from "../../api/client";
import { useAlerts, useNode, useNodes, usePhysical } from "../../api/queries";
import { useCan } from "../../app/auth";
import { Icon } from "../../components/Icon";
import { ErrorState, Lamp, Loading, RelTime } from "../../components/ui";
import { fmtDuration } from "../../lib/format";
import { isUnraid, lampText, nodeLamp, platformLabel } from "../../lib/node";
import { Link, href, navigate, type Route } from "../../lib/router";
import { transitionName } from "../overview/Trackboard";
import { GamingControl } from "./GamingControl";
import { OverviewTab } from "./OverviewTab";
import "./node.css";

const SensorsTab = lazy(() => import("./SensorsTab"));
const NetworkTab = lazy(() => import("./NetworkTab"));
const GamesTab = lazy(() => import("./GamesTab"));
const UpdatesTab = lazy(() => import("./UpdatesTab"));
const ManageTab = lazy(() => import("./ManageTab"));

const TABS = [
  { key: "", label: "Übersicht" },
  { key: "sensoren", label: "Sensoren" },
  { key: "netzwerk", label: "Netzwerk" },
  { key: "spiele", label: "Spiele" },
  { key: "updates", label: "Updates" },
  { key: "verwaltung", label: "Verwaltung" },
] as const;

export default function NodeDetail({ route }: { route: Route }) {
  const nodeId = route.path[1]!;
  const tab = route.params.get("tab") ?? "";
  const node = useNode(nodeId);
  const nodes = useNodes();
  const physical = usePhysical();
  const alerts = useAlerts();
  const can = useCan();

  if (node.isPending) return <Loading label="Gerät wird geladen" />;
  if (node.isError && !node.data) {
    const missing = node.error instanceof ApiError && node.error.status === 404;
    return (
      <div className="stack">
        <Link to="geraete" className="back-link"><Icon name="back" size={16} /> Alle Geräte</Link>
        <ErrorState title={missing ? "Dieses Gerät gibt es nicht (mehr)" : "Gerät nicht erreichbar"} onRetry={missing ? undefined : () => void node.refetch()}>
          {missing ? "Es wurde entfernt oder gehört zu einem anderen Konto." : "Die Daten konnten nicht geladen werden. Prüfe die Verbindung zum Server."}
        </ErrorState>
      </div>
    );
  }
  const data = node.data!;
  const state = nodeLamp(data, alerts.data ?? []);
  const siblings = data.physical_device_id ? (nodes.data ?? []).filter((item) => item.physical_device_id === data.physical_device_id) : [data];
  const device = physical.data?.find((item) => item.device_id === data.physical_device_id);
  const tabHref = (key: string) => `geraete/${encodeURIComponent(nodeId)}${key ? `?tab=${key}` : ""}`;
  const myAlerts = (alerts.data ?? []).filter((alert) => alert.active && alert.node_id === nodeId);

  return (
    <div className="node-detail">
      <Link to="geraete" className="back-link"><Icon name="back" size={16} /> Alle Geräte</Link>
      <header className="node-head">
        <div className="node-title" style={{ viewTransitionName: transitionName(nodeId) } as CSSProperties}>
          <Lamp state={state} size="l" label={lampText(state)} />
          <div>
            <h1>{data.display_name}</h1>
            <p className="node-sub">
              {isUnraid(data) ? "Unraid-Server" : platformLabel(data)}
              {device ? ` · Teil von ${device.display_name}` : ""}
              {data.owner_name ? ` · gehört ${data.owner_name}` : ""}
              {" · "}
              {data.online ? <>online, Rekord-Laufzeit {fmtDuration(data.uptime_record_seconds)}</> : <>Agent offline seit <RelTime iso={data.last_seen_at} /></>}
            </p>
          </div>
        </div>
        <div className="actions">
          <GamingControl node={data} />
        </div>
      </header>

      {siblings.length > 1 && (
        <nav className="profile-switch" aria-label="OS-Profile dieses Geräts">
          <span className="ink-3 small">Weiche:</span>
          {siblings.map((profile) => (
            <a
              key={profile.node_id}
              href={href(`geraete/${encodeURIComponent(profile.node_id)}`)}
              aria-current={profile.node_id === nodeId ? "page" : undefined}
              onClick={(event) => { event.preventDefault(); navigate(`geraete/${encodeURIComponent(profile.node_id)}${tab ? `?tab=${tab}` : ""}`, { replace: true }); }}
            >
              <Lamp state={profile.online ? "go" : "off"} size="s" />
              {platformLabel(profile)}
            </a>
          ))}
        </nav>
      )}

      {myAlerts.length > 0 && (
        <ul className="node-alerts plain" role="list">
          {myAlerts.map((alert) => (
            <li key={alert.alert_id} data-severity={alert.severity}>
              <Lamp state={alert.severity === "critical" ? "stop" : "caution"} size="s" />
              {alert.message} <span className="ink-3">· seit <RelTime iso={alert.opened_at} /></span>
            </li>
          ))}
        </ul>
      )}

      <nav className="tabs" aria-label="Bereiche des Geräts">
        {TABS.map((item) => (
          <a
            key={item.key}
            href={href(tabHref(item.key))}
            aria-current={tab === item.key ? "page" : undefined}
            onClick={(event) => { event.preventDefault(); navigate(tabHref(item.key), { replace: true }); }}
          >
            {item.label}
            {item.key === "verwaltung" && !can.manage(data) && <span className="visually-hidden"> (nur lesen)</span>}
          </a>
        ))}
      </nav>

      <Suspense fallback={<Loading />}>
        {tab === "" && <OverviewTab node={data} />}
        {tab === "sensoren" && <SensorsTab node={data} />}
        {tab === "netzwerk" && <NetworkTab node={data} />}
        {tab === "spiele" && <GamesTab node={data} />}
        {tab === "updates" && <UpdatesTab node={data} />}
        {tab === "verwaltung" && <ManageTab node={data} siblings={siblings} />}
      </Suspense>
    </div>
  );
}
