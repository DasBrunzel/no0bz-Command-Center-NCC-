import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../../api/client";
import { POLL, api, qk } from "../../api/endpoints";
import type { FleetTelemetryPoint } from "../../api/types";

const KEEP = 240;

/**
 * Telemetry history with the server's cursor: the first request loads the
 * last 120 points, later polls ask only for points after the newest one.
 */
export function useTelemetry(nodeId: string, enabled = true) {
  const client = useQueryClient();
  return useQuery({
    queryKey: qk.telemetry(nodeId),
    enabled,
    refetchInterval: POLL.telemetry,
    queryFn: async () => {
      const previous = client.getQueryData<FleetTelemetryPoint[]>(qk.telemetry(nodeId));
      const last = previous?.[previous.length - 1];
      if (!last) return api.fleet.telemetry(nodeId, 120);
      try {
        const fresh = await api.fleet.telemetry(nodeId, 120, last.point_id);
        if (!fresh.length) return previous;
        return [...previous, ...fresh].slice(-KEEP);
      } catch (error) {
        // The cursor point was pruned: start over.
        if (error instanceof ApiError && error.status === 404) return api.fleet.telemetry(nodeId, 120);
        throw error;
      }
    },
  });
}
