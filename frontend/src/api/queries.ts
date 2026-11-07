import { QueryClient, keepPreviousData, useMutation, useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query";
import { ApiError } from "./client";
import { POLL, api, qk } from "./endpoints";

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 2_000,
        // Polling stops while the tab is hidden and resumes on focus.
        refetchIntervalInBackground: false,
        refetchOnWindowFocus: true,
        retry: (count, error) => {
          if (error instanceof ApiError && [401, 403, 404, 410, 422].includes(error.status)) return false;
          return count < 2;
        },
        retryDelay: (attempt) => Math.min(8_000, 1_000 * 2 ** attempt),
      },
      mutations: { retry: false },
    },
  });
}

export const useVersion = () => useQuery({ queryKey: qk.version, queryFn: api.version, staleTime: 10 * 60_000 });
export const useSummary = () => useQuery({ queryKey: qk.summary, queryFn: api.fleet.summary, refetchInterval: POLL.summary });
export const useNodes = () => useQuery({ queryKey: qk.nodes, queryFn: api.fleet.nodes, refetchInterval: POLL.nodes });
export const useAlerts = () => useQuery({ queryKey: qk.alerts, queryFn: () => api.fleet.alerts(200), refetchInterval: POLL.alerts });
export const useGroups = () => useQuery({ queryKey: qk.groups, queryFn: api.fleet.groups, refetchInterval: POLL.admin });
export const usePhysical = () => useQuery({ queryKey: qk.physical, queryFn: api.fleet.physicalDevices, refetchInterval: POLL.admin });
export const useNode = (nodeId: string) =>
  useQuery({ queryKey: qk.node(nodeId), queryFn: () => api.fleet.node(nodeId), refetchInterval: POLL.nodes });
export const useNetworkHistory = (nodeId: string | null, limit = 60) =>
  useQuery({
    queryKey: [...qk.networkHistory(nodeId ?? "-"), limit],
    queryFn: () => api.fleet.networkHistory(nodeId!, limit),
    enabled: !!nodeId,
    refetchInterval: POLL.networkHistory,
    placeholderData: keepPreviousData,
  });
export const useFleetNetwork = (minutes = 30) =>
  useQuery({ queryKey: qk.fleetNetwork(minutes), queryFn: () => api.fleet.network(minutes), refetchInterval: POLL.fleetNetwork, placeholderData: keepPreviousData });
export const useNetworkMonth = (nodeId: string) =>
  useQuery({ queryKey: qk.networkMonth(nodeId), queryFn: () => api.fleet.networkMonth(nodeId), refetchInterval: POLL.networkMonth });
export const useHardwareStats = (days: number, nodeId: string | null) =>
  useQuery({ queryKey: qk.hardwareStats(days, nodeId), queryFn: () => api.fleet.hardwareStats(days, nodeId), refetchInterval: POLL.hardwareStats, placeholderData: keepPreviousData });
export const useGames = () => useQuery({ queryKey: qk.games, queryFn: api.games.list, refetchInterval: POLL.games });
export const useGameStats = (days: number, nodeId: string | null) =>
  useQuery({ queryKey: qk.gameStats(days, nodeId), queryFn: () => api.games.stats(days, nodeId), refetchInterval: POLL.games, placeholderData: keepPreviousData });

/** Mutation that invalidates the given keys and reports through callbacks. */
export function useAction<TArgs, TResult>(
  fn: (args: TArgs) => Promise<TResult>,
  invalidate: QueryKey[] = [],
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: async () => {
      await Promise.all(invalidate.map((queryKey) => client.invalidateQueries({ queryKey })));
    },
  });
}
