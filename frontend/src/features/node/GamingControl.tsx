import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, qk } from "../../api/endpoints";
import type { FleetNode } from "../../api/types";
import { useCan } from "../../app/auth";
import { Icon } from "../../components/Icon";
import { useToast } from "../../components/toast";
import { Menu, useNow } from "../../components/ui";
import { fmtTime, minutesUntil } from "../../lib/format";
import { gamingUntil } from "../../lib/node";

const DURATIONS = [30, 60, 120, 240, 480];

/** Gaming Mode on/off with a duration; locked for roles the server rejects. */
export function GamingControl({ node, compact }: { node: FleetNode; compact?: boolean }) {
  const can = useCan();
  const client = useQueryClient();
  const toast = useToast();
  const now = useNow();
  const [busy, setBusy] = useState(false);
  const until = gamingUntil(node, now);
  const allowed = can.gaming(node);

  const set = async (minutes: number) => {
    setBusy(true);
    try {
      const updated = await api.fleet.setGamingMode(node.node_id, minutes);
      client.setQueryData<FleetNode[]>(qk.nodes, (list) => list?.map((item) => (item.node_id === updated.node_id ? updated : item)));
      client.setQueryData(qk.node(node.node_id), updated);
      toast.ok(minutes ? `Gaming Mode für ${node.display_name} bis ${fmtTime(updated.gaming_mode_until)}. Last-Warnungen ruhen so lange.` : `Gaming Mode für ${node.display_name} beendet.`);
    } catch (error) {
      toast.fail(error, "Gaming Mode konnte nicht geändert werden.");
    } finally {
      setBusy(false);
    }
  };

  const label = until ? `Gaming bis ${fmtTime(until)}` : "Gaming Mode";
  if (!allowed) {
    return (
      <button type="button" className={`btn ${compact ? "btn-s" : ""}`} disabled title="Nur Commander, Beta-Tester oder der Besitzer des Geräts.">
        <Icon name="gamepad" /> {until ? label : "Gaming Mode"} <span className="visually-hidden">(gesperrt)</span>
      </button>
    );
  }
  return (
    <Menu label="Gaming Mode schalten" icon="gamepad" text={label} buttonClass={`btn ${compact ? "btn-s" : ""} gaming-button${until ? " is-on" : ""}`} align="start">
      <p className="menu-note">Im Gaming Mode schweigen CPU- und GPU-Last-Warnungen. Temperaturwarnungen bleiben aktiv.</p>
      {DURATIONS.map((minutes) => (
        <button key={minutes} type="button" className="menu-item" role="menuitem" disabled={busy} onClick={() => void set(minutes)}>
          {minutes < 60 ? `${minutes} Minuten` : `${minutes / 60} ${minutes === 60 ? "Stunde" : "Stunden"}`}
        </button>
      ))}
      {until && (
        <>
          <hr />
          <button type="button" className="menu-item" role="menuitem" disabled={busy} onClick={() => void set(0)}>
            Beenden (noch {minutesUntil(until, now)} min)
          </button>
        </>
      )}
    </Menu>
  );
}
