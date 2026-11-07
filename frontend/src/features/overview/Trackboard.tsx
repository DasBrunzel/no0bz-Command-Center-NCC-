import type { CSSProperties } from "react";
import type { FleetAlert, FleetGroup } from "../../api/types";
import { Lamp, Meter, RelTime, useNow } from "../../components/ui";
import { fmtTime } from "../../lib/format";
import { cpuPercent, gamingUntil, gpuPercent, groupLabel, isUnraid, lampText, memPercent, nodeLamp, platformLabel, type Machine } from "../../lib/node";
import { Link } from "../../lib/router";

export function transitionName(nodeId: string): string {
  return `n-${nodeId.replace(/[^a-zA-Z0-9_-]/g, "")}`;
}

interface Props {
  machines: Machine[];
  groups: FleetGroup[];
  alerts: FleetAlert[];
  onlineOnly: boolean;
}

/** The fleet as a track diagram: one track per group, one block per machine. */
export function Trackboard({ machines, groups, alerts, onlineOnly }: Props) {
  const sorted = [...groups].sort((a, b) => a.position - b.position || a.name.localeCompare(b.name, "de"));
  const known = new Set(sorted.map((group) => group.group_id));
  const tracks = [
    ...sorted.map((group) => ({ id: group.group_id, name: groupLabel(group) })),
    { id: "__other", name: "Weitere Geräte" },
  ];
  const visible = machines.filter((machine) => !onlineOnly || machine.profiles.some((node) => node.online));
  const byTrack = (trackId: string) =>
    visible.filter((machine) => (known.has(machine.active.fleet_group_id) ? machine.active.fleet_group_id === trackId : trackId === "__other"));

  const filled = tracks.map((track) => ({ ...track, machines: byTrack(track.id) })).filter((track) => track.machines.length);
  if (!filled.length) return <p className="ink-3">Gerade ist kein Gerät online.</p>;

  return (
    <div className="trackboard">
      {filled.map((track) => (
        <section key={track.id} className="track" aria-label={`Gleis ${track.name}`}>
          <h3 className="track-name">{track.name}</h3>
          <ol className="track-line plain" role="list">
            {track.machines.map((machine) => (
              <li key={machine.key}>
                <Block machine={machine} alerts={alerts} />
              </li>
            ))}
          </ol>
        </section>
      ))}
    </div>
  );
}

function Block({ machine, alerts }: { machine: Machine; alerts: FleetAlert[] }) {
  const now = useNow();
  const node = machine.active;
  const state = nodeLamp(node, alerts);
  const metrics = node.online ? node.latest?.metrics : null;
  const until = gamingUntil(node, now);
  const dual = machine.profiles.length > 1;
  const cpu = cpuPercent(metrics);
  const ram = memPercent(metrics);
  const gpu = gpuPercent(metrics);
  return (
    <article
      className="block"
      data-state={state}
      data-dual={dual || undefined}
      style={{ viewTransitionName: transitionName(node.node_id) } as CSSProperties}
    >
      <header className="block-head">
        <Lamp state={state} label={lampText(state)} />
        <h4>
          <Link to={`geraete/${encodeURIComponent(node.node_id)}`} className="block-link">{machine.name}</Link>
        </h4>
        <span className="block-platform">{isUnraid(node) ? "Unraid" : dual ? "Dualboot" : platformLabel(node)}</span>
      </header>

      {dual && <Turnout machine={machine} />}

      {node.online ? (
        <dl className="block-meters">
          <div><dt>CPU</dt><dd><Meter value={cpu} label={`CPU ${machine.name}`} /><span className="num">{cpu == null ? "–" : Math.round(cpu)}</span></dd></div>
          <div><dt>RAM</dt><dd><Meter value={ram} label={`RAM ${machine.name}`} /><span className="num">{ram == null ? "–" : Math.round(ram)}</span></dd></div>
          {gpu != null && <div className="block-gpu"><dt>GPU</dt><dd><Meter value={gpu} label={`GPU ${machine.name}`} /><span className="num">{Math.round(gpu)}</span></dd></div>}
        </dl>
      ) : null}

      <p className="block-foot">
        {!node.online ? (
          <>Offline seit <RelTime iso={node.last_seen_at} /></>
        ) : node.now_playing?.title ? (
          <>Spielt <b>{node.now_playing.title}</b></>
        ) : until ? (
          <>Gaming Mode bis {fmtTime(until)}</>
        ) : (
          <>Läuft · {node.agent_version ? `Agent ${node.agent_version}` : "Agent"}</>
        )}
      </p>
    </article>
  );
}

/**
 * Dual boot as a turnout: the straight line and the branch are the OS
 * profiles, and the one that is running is the thrown, lit route.
 */
function Turnout({ machine }: { machine: Machine }) {
  const [straight, branch, ...more] = machine.profiles;
  const activeId = machine.profiles.find((node) => node.online)?.node_id ?? null;
  const thrown = activeId && branch && activeId === branch.node_id ? "branch" : activeId ? "straight" : "none";
  return (
    <div className="turnout" data-thrown={thrown}>
      <svg viewBox="0 0 120 44" preserveAspectRatio="none" aria-hidden="true">
        <path className="turnout-straight" d="M0 34H120" />
        <path className="turnout-branch" d="M18 34C48 34 52 10 82 10H120" />
      </svg>
      <ul className="turnout-routes plain" role="list" aria-label="OS-Profile">
        {[branch, straight, ...more].filter(Boolean).map((profile) => (
          <li key={profile!.node_id} data-active={profile!.node_id === activeId || undefined}>
            <Lamp state={profile!.online ? "go" : "off"} size="s" />
            <Link to={`geraete/${encodeURIComponent(profile!.node_id)}`}>{platformLabel(profile!)}</Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
