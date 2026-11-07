import { useDeferredValue, useMemo, useState, type CSSProperties } from "react";
import { useAlerts, useGroups, useNodes, usePhysical } from "../../api/queries";
import type { FleetAlert, FleetNode } from "../../api/types";
import { useCan } from "../../app/auth";
import { Icon } from "../../components/Icon";
import { Empty, ErrorState, Lamp, Loading, Meter, PageHead, Reading, RelTime } from "../../components/ui";
import { plural } from "../../lib/format";
import { cpuPercent, cpuTemp, down, gamingUntil, gpuPercent, gpuTemp, groupLabel, lampText, machinesOf, memPercent, nodeLamp, platformLabel, sortByLayout, up, type Machine } from "../../lib/node";
import { Link, navigate, type Route } from "../../lib/router";
import { transitionName } from "../overview/Trackboard";
import { LayoutDialog } from "./LayoutDialog";
import "./fleet.css";

type StatusFilter = "all" | "online" | "offline" | "alert" | "gaming";
const STATUS: Array<{ key: StatusFilter; label: string }> = [
  { key: "all", label: "Alle" },
  { key: "online", label: "Online" },
  { key: "offline", label: "Offline" },
  { key: "alert", label: "Mit Warnung" },
  { key: "gaming", label: "Gaming" },
];

export default function Fleet({ route }: { route: Route }) {
  const nodes = useNodes();
  const groups = useGroups();
  const physical = usePhysical();
  const alerts = useAlerts();
  const can = useCan();
  const [query, setQuery] = useState(route.params.get("q") ?? "");
  const [status, setStatus] = useState<StatusFilter>((route.params.get("status") as StatusFilter) || "all");
  const [group, setGroup] = useState(route.params.get("gruppe") ?? "");
  const [arranging, setArranging] = useState(false);
  const deferred = useDeferredValue(query.trim().toLowerCase());
  const active = useMemo(() => (alerts.data ?? []).filter((alert) => alert.active), [alerts.data]);

  const machines = useMemo(() => machinesOf([...(nodes.data ?? [])].sort(sortByLayout), physical.data), [nodes.data, physical.data]);
  const filtered = useMemo(() => machines.filter((machine) => {
    const profiles = machine.profiles;
    if (group && machine.active.fleet_group_id !== group) return false;
    if (status === "online" && !profiles.some((node) => node.online)) return false;
    if (status === "offline" && profiles.some((node) => node.online)) return false;
    if (status === "alert" && !profiles.some((node) => active.some((alert) => alert.node_id === node.node_id))) return false;
    if (status === "gaming" && !profiles.some((node) => gamingUntil(node))) return false;
    if (!deferred) return true;
    const haystack = [machine.name, ...profiles.flatMap((node) => [node.display_name, platformLabel(node), node.owner_name ?? "", node.latest?.metrics.cpu?.model ?? "", node.latest?.metrics.gpus?.[0]?.name ?? "", node.agent_version ?? ""])].join(" ").toLowerCase();
    return haystack.includes(deferred);
  }), [machines, group, status, deferred, active]);

  if (nodes.isPending) return <Loading label="Geräte werden geladen" />;
  if (nodes.isError && !nodes.data) return <ErrorState title="Server nicht erreichbar" onRetry={() => void nodes.refetch()}>Die Geräteliste kann gerade nicht geladen werden.</ErrorState>;

  const groupName = (id: string) => { const group = groups.data?.find((item) => item.group_id === id); return group ? groupLabel(group) : "Weitere"; };
  const total = nodes.data?.length ?? 0;
  const sortedGroups = [...(groups.data ?? [])].sort((a, b) => a.position - b.position);

  return (
    <div className="fleet">
      <PageHead
        title="Geräte"
        lead={`${plural(machines.length, "physisches Gerät", "physische Geräte")}, ${plural(total, "OS-Profil", "OS-Profile")}.`}
        actions={
          <>
            <Link to="hardware" className="btn"><Icon name="hardware" /> Hardware-Statistik</Link>
            {can.commander && <button type="button" className="btn" onClick={() => setArranging(true)}><Icon name="fleet" /> Anordnen</button>}
            {can.team && <Link to="aufnahme" className="btn btn-primary"><Icon name="plus" /> Gerät aufnehmen</Link>}
          </>
        }
      />

      <div className="filters" role="search">
        <label className="field filters-search">
          <span className="visually-hidden">Geräte durchsuchen</span>
          <span className="input-icon"><Icon name="search" size={18} /></span>
          <input className="input" type="search" placeholder="Name, Besitzer, CPU, GPU …" value={query} onChange={(event) => setQuery(event.target.value)} />
        </label>
        <div className="segmented" role="radiogroup" aria-label="Status">
          {STATUS.map((item) => (
            <label key={item.key}>
              <input type="radio" name="status" checked={status === item.key} onChange={() => setStatus(item.key)} />
              <span>{item.label}</span>
            </label>
          ))}
        </div>
        <label className="field">
          <span className="visually-hidden">Gruppe</span>
          <select className="select" value={group} onChange={(event) => setGroup(event.target.value)}>
            <option value="">Alle Gruppen</option>
            {sortedGroups.map((item) => <option key={item.group_id} value={item.group_id}>{groupLabel(item)}</option>)}
          </select>
        </label>
      </div>

      {total === 0 ? (
        <Empty title="Noch keine Geräte" icon="enroll" action={can.team ? <Link to="aufnahme" className="btn btn-s">Gerät aufnehmen</Link> : undefined}>
          Installiere den NCC-Agent auf einem PC und koppel ihn – dann taucht er hier auf.
        </Empty>
      ) : filtered.length === 0 ? (
        <Empty title="Kein Gerät passt zu diesem Filter" icon="search" action={<button type="button" className="btn btn-s" onClick={() => { setQuery(""); setStatus("all"); setGroup(""); }}>Filter zurücksetzen</button>} />
      ) : (
        <div className="panel fleet-table-panel">
          <div className="table-wrap">
            <table className="table fleet-table">
              <caption className="visually-hidden">Geräte und ihre aktuellen Messwerte</caption>
              <thead>
                <tr>
                  <th>Gerät</th>
                  <th className="col-m">Gruppe</th>
                  <th>CPU</th>
                  <th className="col-m">RAM</th>
                  <th className="col-l">GPU</th>
                  <th className="col-l r">Temp. CPU / GPU</th>
                  <th className="col-l r">Netz ↓ / ↑</th>
                  <th className="col-m">Besitzer</th>
                  <th className="r">Zuletzt</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((machine) => <MachineRows key={machine.key} machine={machine} groupName={groupName(machine.active.fleet_group_id)} alerts={active} />)}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {arranging && (
        <LayoutDialog
          nodes={nodes.data ?? []}
          groups={sortedGroups}
          onClose={() => setArranging(false)}
        />
      )}
    </div>
  );
}

function MachineRows({ machine, groupName, alerts }: { machine: Machine; groupName: string; alerts: FleetAlert[] }) {
  const dual = machine.profiles.length > 1;
  return (
    <>
      {dual && (
        <tr className="machine-row">
          <td colSpan={9}>
            <span className="machine-name"><Icon name="switch" size={16} /> {machine.name}</span>
            <span className="ink-3 small"> · Dualboot mit {machine.profiles.map((node) => platformLabel(node)).join(" und ")}</span>
          </td>
        </tr>
      )}
      {machine.profiles.map((node) => <NodeRow key={node.node_id} node={node} groupName={groupName} alerts={alerts} nested={dual} />)}
    </>
  );
}

function NodeRow({ node, groupName, alerts, nested }: { node: FleetNode; groupName: string; alerts: FleetAlert[]; nested: boolean }) {
  const state = nodeLamp(node, alerts);
  const m = node.online ? node.latest?.metrics : null;
  const cpu = cpuPercent(m);
  const ram = memPercent(m);
  const gpu = gpuPercent(m);
  const href = `geraete/${encodeURIComponent(node.node_id)}`;
  return (
    <tr data-state={state} data-nested={nested || undefined} onClick={(event) => { if (!(event.target as HTMLElement).closest("a, button")) navigate(href); }}>
      <td>
        <span className="node-cell" style={{ viewTransitionName: transitionName(node.node_id) } as CSSProperties}>
          <Lamp state={state} label={lampText(state)} />
          <span>
            <Link to={href} className="node-link">{nested ? platformLabel(node) : node.display_name}</Link>
            <small>{nested ? node.display_name : platformLabel(node)}{node.now_playing?.title ? ` · spielt ${node.now_playing.title}` : ""}</small>
          </span>
        </span>
      </td>
      <td className="col-m">{groupName}</td>
      <td><MeterCell value={cpu} label="CPU" /></td>
      <td className="col-m"><MeterCell value={ram} label="RAM" /></td>
      <td className="col-l"><MeterCell value={gpu} label="GPU" /></td>
      <td className="col-l r nowrap"><Reading value={cpuTemp(m)} unit="°C" /> / <Reading value={gpuTemp(m)} unit="°C" /></td>
      <td className="col-l r nowrap"><Reading value={down(m)} unit="" digits={1} /> / <Reading value={up(m)} unit="Mbit/s" digits={1} /></td>
      <td className="col-m">{node.owner_name ?? <span className="ink-3">–</span>}</td>
      <td className="r nowrap">{node.online ? <span className="ink-3">jetzt</span> : <RelTime iso={node.last_seen_at} />}</td>
    </tr>
  );
}

function MeterCell({ value, label }: { value: number | null; label: string }) {
  if (value == null) return <span className="ink-3">–</span>;
  return (
    <span className="meter-cell">
      <Meter value={value} label={label} />
      <span className="num">{Math.round(value)}<span className="unit">%</span></span>
    </span>
  );
}
