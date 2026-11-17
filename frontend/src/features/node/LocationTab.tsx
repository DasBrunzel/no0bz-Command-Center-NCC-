import { useQuery, useQueryClient } from "@tanstack/react-query";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef, useState } from "react";
import { api, qk } from "../../api/endpoints";
import type { FleetNode, LocationHeatmap } from "../../api/types";
import { useCan } from "../../app/auth";
import { useToast } from "../../components/toast";
import { ConfirmDialog, DaysPicker, Empty, ErrorState, Loading, RelTime } from "../../components/ui";
import { HeatLayer } from "./heatLayer";

/** "Alles" in the days picker means every stored point. */
const ALL_DAYS = 3660;

export default function LocationTab({ node }: { node: FleetNode }) {
  const can = useCan();
  const toast = useToast();
  const client = useQueryClient();
  const manageable = can.manage(node);
  const [range, setRange] = useState(30);
  const days = range === 0 ? ALL_DAYS : range;
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const tracking = !!node.location_tracking;
  const heat = useQuery({ queryKey: qk.locations(node.node_id, days), queryFn: () => api.fleet.locations(node.node_id, days), refetchInterval: 60_000 });

  const toggle = async () => {
    setBusy(true);
    try {
      await api.fleet.setLocationTracking(node.node_id, !tracking);
      await client.invalidateQueries({ queryKey: qk.node(node.node_id) });
      toast.ok(tracking ? "Standortverlauf ist aus. Das Handy sammelt keine Standorte mehr." : "Standortverlauf ist an. Das Handy fragt beim nächsten Öffnen nach der Standort-Berechtigung.");
    } catch (error) {
      toast.fail(error);
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    setBusy(true);
    try {
      const result = await api.fleet.deleteLocations(node.node_id);
      await client.invalidateQueries({ queryKey: ["fleet", "locations", node.node_id] });
      toast.ok(`${result.deleted} Standortpunkte gelöscht.`);
      setConfirmDelete(false);
    } catch (error) {
      toast.fail(error);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      <section className="panel" aria-labelledby="location-title">
        <div className="panel-head">
          <h2 id="location-title">Standort-Heatmap</h2>
          <p>{tracking ? "Verlauf wird aufgezeichnet" : "Verlauf ist aus"}</p>
        </div>
        <div className="location-bar">
          <label className="switch">
            <input type="checkbox" checked={tracking} disabled={!manageable || busy} onChange={() => void toggle()} />
            Standortverlauf aufzeichnen
          </label>
          <DaysPicker value={range} onChange={setRange} />
        </div>
        <p className="form-hint mt-4">
          Das Handy hängt seinen Standort an die normalen Messwerte; gespeichert wird er nur, solange der Schalter an ist –
          auch in der App umschaltbar. Die Punkte bleiben, bis du sie löschst.
        </p>
      </section>

      {heat.isPending ? (
        <Loading label="Standorte werden geladen" />
      ) : heat.isError && !heat.data ? (
        <ErrorState onRetry={() => void heat.refetch()}>Der Standortverlauf konnte nicht geladen werden.</ErrorState>
      ) : heat.data!.points === 0 ? (
        <Empty title="Keine Standorte im Zeitraum" icon="info">
          {tracking
            ? "Sobald das Handy Messwerte mit Standort hochlädt, erscheinen sie hier. Bei der Upload-Regel „WLAN + Laden“ kann das bis zum nächsten Laden dauern."
            : "Schalte den Standortverlauf ein, um eine Heatmap zu sammeln."}
        </Empty>
      ) : (
        <HeatMap data={heat.data!} />
      )}

      {heat.data && heat.data.stored_points > 0 && (
        <section className="panel">
          <div className="panel-head"><h2>Daten</h2></div>
          <p className="small">
            {heat.data.points} Punkte im Zeitraum
            {heat.data.first_at && heat.data.last_at && <> · <RelTime iso={heat.data.first_at} prefix="von " /> bis <RelTime iso={heat.data.last_at} /></>}
            {" · "}{heat.data.stored_points} insgesamt gespeichert
          </p>
          <div className="actions mt-4">
            <a className="btn" href={api.fleet.locationsGpxUrl(node.node_id, days)} download>GPX herunterladen</a>
            {manageable && <button type="button" className="btn btn-danger" disabled={busy} onClick={() => setConfirmDelete(true)}>Verlauf löschen</button>}
          </div>
        </section>
      )}

      <ConfirmDialog
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => void remove()}
        title="Standortverlauf löschen?"
        confirmLabel="Endgültig löschen"
        danger
        busy={busy}
      >
        Alle {heat.data?.stored_points ?? 0} gespeicherten Standortpunkte von {node.display_name} werden vom Server gelöscht. Das lässt sich nicht rückgängig machen.
      </ConfirmDialog>
    </div>
  );
}

function HeatMap({ data }: { data: LocationHeatmap }) {
  const element = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<HeatLayer | null>(null);

  useEffect(() => {
    if (!element.current) return;
    // Kein Mausrad-Zoom: Auf der langen Seite soll das Rad die Seite scrollen, nicht die Karte.
    const instance = L.map(element.current, { zoomControl: true, attributionControl: true, worldCopyJump: true, scrollWheelZoom: false });
    // Tiles come through the NCC server (the dashboard only loads images from itself).
    L.tileLayer("/api/v1/map/tiles/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a>-Mitwirkende',
    }).addTo(instance);
    layer.current = new HeatLayer([]).addTo(instance);
    map.current = instance;
    return () => {
      instance.remove();
      map.current = null;
      layer.current = null;
    };
  }, []);

  useEffect(() => {
    if (!map.current || !layer.current) return;
    layer.current.setCells(data.cells);
    const bounds = L.latLngBounds(data.cells.map(([lat, lon]) => [lat, lon] as [number, number]));
    if (bounds.isValid()) map.current.fitBounds(bounds, { padding: [32, 32], maxZoom: 16 });
  }, [data]);

  return <div ref={element} className="location-map" role="img" aria-label={`Heatmap mit ${data.points} Standortpunkten`} />;
}
