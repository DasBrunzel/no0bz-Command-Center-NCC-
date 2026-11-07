import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, qk } from "../../api/endpoints";
import type { FleetGroup, FleetNode } from "../../api/types";
import { Icon } from "../../components/Icon";
import { useToast } from "../../components/toast";
import { Dialog } from "../../components/ui";
import { groupLabel, sortByLayout } from "../../lib/node";

/** Commander only: move nodes between groups, reorder them, add groups. */
export function LayoutDialog({ nodes, groups, onClose }: { nodes: FleetNode[]; groups: FleetGroup[]; onClose: () => void }) {
  const client = useQueryClient();
  const toast = useToast();
  const [allGroups, setAllGroups] = useState(groups);
  const [order, setOrder] = useState(() => {
    const map: Record<string, string[]> = Object.fromEntries(groups.map((group) => [group.group_id, [] as string[]]));
    for (const node of [...nodes].sort(sortByLayout)) {
      const key = map[node.fleet_group_id] ? node.fleet_group_id : groups[0]?.group_id;
      if (key) map[key]!.push(node.node_id);
    }
    return map;
  });
  const [newGroup, setNewGroup] = useState("");
  const [busy, setBusy] = useState(false);
  const byId = new Map(nodes.map((node) => [node.node_id, node]));

  const move = (groupId: string, index: number, delta: number) => {
    setOrder((current) => {
      const list = [...current[groupId]!];
      const target = index + delta;
      if (target < 0 || target >= list.length) return current;
      [list[index], list[target]] = [list[target]!, list[index]!];
      return { ...current, [groupId]: list };
    });
  };
  const reassign = (nodeId: string, from: string, to: string) => {
    setOrder((current) => ({ ...current, [from]: current[from]!.filter((id) => id !== nodeId), [to]: [...(current[to] ?? []), nodeId] }));
  };

  const addGroup = async () => {
    const name = newGroup.trim();
    if (!name) return;
    setBusy(true);
    try {
      const group = await api.fleet.createGroup(name);
      setAllGroups((list) => [...list, group]);
      setOrder((current) => ({ ...current, [group.group_id]: [] }));
      setNewGroup("");
      await client.invalidateQueries({ queryKey: qk.groups });
      toast.ok(`Gruppe „${group.name}“ angelegt.`);
    } catch (error) {
      toast.fail(error, "Die Gruppe konnte nicht angelegt werden.");
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    const placements = Object.entries(order).flatMap(([group_id, ids]) => ids.map((node_id, position) => ({ node_id, group_id, position })));
    if (!placements.length) return onClose();
    setBusy(true);
    try {
      await api.fleet.saveLayout(placements);
      await client.invalidateQueries({ queryKey: qk.nodes });
      toast.ok("Anordnung gespeichert.");
      onClose();
    } catch (error) {
      toast.fail(error, "Die Anordnung konnte nicht gespeichert werden.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title="Geräte anordnen"
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>Abbrechen</button>
          <button type="button" className="btn btn-primary" onClick={() => void save()} disabled={busy}>Anordnung speichern</button>
        </>
      }
    >
      <p className="form-hint">Jede Gruppe ist ein Gleis in der Lage. Die Reihenfolge hier ist die Reihenfolge auf dem Gleis.</p>
      <div className="layout-groups">
        {allGroups.map((group) => (
          <section key={group.group_id} className="layout-group" aria-label={`Gruppe ${groupLabel(group)}`}>
            <h3>{groupLabel(group)}</h3>
            {(order[group.group_id] ?? []).length === 0 ? (
              <p className="ink-3 small">Noch leer.</p>
            ) : (
              <ol className="plain layout-list" role="list">
                {order[group.group_id]!.map((nodeId, index, list) => {
                  const node = byId.get(nodeId);
                  if (!node) return null;
                  return (
                    <li key={nodeId}>
                      <span className="grow">{node.display_name}</span>
                      <label className="visually-hidden" htmlFor={`group-${nodeId}`}>Gruppe für {node.display_name}</label>
                      <select id={`group-${nodeId}`} className="select layout-select" value={group.group_id} onChange={(event) => reassign(nodeId, group.group_id, event.target.value)}>
                        {allGroups.map((option) => <option key={option.group_id} value={option.group_id}>{groupLabel(option)}</option>)}
                      </select>
                      <button type="button" className="btn btn-quiet btn-icon btn-s" onClick={() => move(group.group_id, index, -1)} disabled={index === 0} aria-label={`${node.display_name} nach vorne`}><Icon name="chevron" style={{ rotate: "-90deg" }} /></button>
                      <button type="button" className="btn btn-quiet btn-icon btn-s" onClick={() => move(group.group_id, index, 1)} disabled={index === list.length - 1} aria-label={`${node.display_name} nach hinten`}><Icon name="chevron" style={{ rotate: "90deg" }} /></button>
                    </li>
                  );
                })}
              </ol>
            )}
          </section>
        ))}
      </div>
      <form className="row" onSubmit={(event) => { event.preventDefault(); void addGroup(); }}>
        <label className="field grow">
          <span>Neue Gruppe</span>
          <input className="input" maxLength={64} value={newGroup} onChange={(event) => setNewGroup(event.target.value)} placeholder="z. B. Wohnzimmer" />
        </label>
        <button type="submit" className="btn" disabled={busy || !newGroup.trim()} style={{ alignSelf: "end" }}><Icon name="plus" /> Gruppe anlegen</button>
      </form>
    </Dialog>
  );
}
