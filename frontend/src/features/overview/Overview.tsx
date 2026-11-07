import { useMemo, useState } from "react";
import { useAlerts, useGroups, useNodes, usePhysical, useSummary } from "../../api/queries";
import { useCan } from "../../app/auth";
import { Empty, ErrorState, Loading } from "../../components/ui";
import { fmtInt, plural } from "../../lib/format";
import { gamingUntil, machinesOf, sortByLayout } from "../../lib/node";
import type { Route } from "../../lib/router";
import { Annunciator } from "./Annunciator";
import { LiveTraffic } from "./LiveTraffic";
import { Trackboard } from "./Trackboard";
import "./overview.css";

export default function Overview(_: { route: Route }) {
  const nodes = useNodes();
  const groups = useGroups();
  const physical = usePhysical();
  const alerts = useAlerts();
  const summary = useSummary();
  const can = useCan();
  const [filter, setFilter] = useState<"all" | "online">("all");

  const list = useMemo(() => [...(nodes.data ?? [])].sort(sortByLayout), [nodes.data]);
  const active = (alerts.data ?? []).filter((alert) => alert.active);
  const machines = useMemo(() => machinesOf(list, physical.data), [list, physical.data]);
  const gaming = list.filter((node) => gamingUntil(node)).length;
  const online = machines.filter((machine) => machine.profiles.some((node) => node.online)).length;
  const playing = list.filter((node) => node.online && node.now_playing);

  if (nodes.isPending) return <Loading label="Lage wird geladen" />;
  if (nodes.isError && !nodes.data) return <ErrorState title="Server nicht erreichbar" onRetry={() => void nodes.refetch()}>Die Lage kann gerade nicht abgefragt werden. Prüfe Tailscale oder ob der NCC-Server läuft.</ErrorState>;

  const critical = active.filter((alert) => alert.severity === "critical").length;
  return (
    <div className="overview">
      <header className="situation">
        <h1>
          <span className="situation-line">
            {machines.length === 0 ? "Noch kein Gerät auf dem Gleis." : `${fmtInt(online)} von ${plural(machines.length, "Gerät", "Geräten")} online.`}
          </span>
          <span className="situation-line situation-sub" data-tone={critical ? "stop" : active.length ? "caution" : "go"}>
            {critical
              ? `${plural(critical, "kritische Störung", "kritische Störungen")}${active.length > critical ? `, ${plural(active.length - critical, "Warnung", "Warnungen")}` : ""}.`
              : active.length ? `${plural(active.length, "Warnung", "Warnungen")} offen.` : "Keine Störung, alle Signale auf Fahrt."}
          </span>
        </h1>
        <dl className="situation-facts">
          <div><dt>OS-Profile</dt><dd className="num">{fmtInt(list.length)}</dd></div>
          <div><dt>Gaming Mode</dt><dd className="num">{fmtInt(gaming)}</dd></div>
          <div><dt>Es spielt gerade</dt><dd>{playing.length ? playing.map((node) => node.now_playing?.title).filter(Boolean).slice(0, 2).join(", ") || fmtInt(playing.length) : "niemand"}</dd></div>
          <div><dt>Wartet auf Freigabe</dt><dd className="num">{fmtInt(summary.data?.pending_nodes ?? 0)}</dd></div>
          <div><dt>Telemetrie-Punkte</dt><dd className="num">{summary.data ? fmtInt(summary.data.telemetry_points) : "–"}</dd></div>
        </dl>
      </header>

      <section className="section" aria-labelledby="track-title">
        <div className="section-title">
          <h2 id="track-title">Gleisbild</h2>
          <div className="segmented" role="radiogroup" aria-label="Geräte zeigen">
            <label><input type="radio" name="track-filter" checked={filter === "all"} onChange={() => setFilter("all")} /><span>Alle</span></label>
            <label><input type="radio" name="track-filter" checked={filter === "online"} onChange={() => setFilter("online")} /><span>Nur online</span></label>
          </div>
        </div>
        {list.length === 0 ? (
          <Empty title="Noch keine Geräte" icon="enroll" action={can.team ? <a className="btn btn-s" href="#/aufnahme">Gerät aufnehmen</a> : undefined}>
            Sobald ein Agent gekoppelt ist, erscheint er hier als Gleisabschnitt.
          </Empty>
        ) : (
          <Trackboard machines={machines} groups={groups.data ?? []} alerts={active} onlineOnly={filter === "online"} />
        )}
      </section>

      <div className="overview-split">
        <Annunciator alerts={alerts.data ?? []} loading={alerts.isPending} error={alerts.isError && !alerts.data} onRetry={() => void alerts.refetch()} />
        <LiveTraffic />
      </div>
    </div>
  );
}
