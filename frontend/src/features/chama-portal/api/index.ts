import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api-client";
import type { Page } from "@/lib/pagination";
import type { ChamaGroup, ChamaMember, Contribution, Payout } from "@/features/chama-portal/types";

export function useMyChamas() {
  return useQuery({
    queryKey: ["chama", "groups"],
    queryFn: async () => (await apiClient.get<Page<ChamaGroup>>("/chama/groups", { params: { limit: 200 } })).data.items,
  });
}

export function useChamaMembers(chamaId: string | null) {
  return useQuery({
    queryKey: ["chama", "members", chamaId],
    queryFn: async () => (await apiClient.get<Page<ChamaMember>>(`/chama/groups/${chamaId}/members`, { params: { limit: 200 } })).data.items,
    enabled: !!chamaId,
  });
}

export function usePunctuality(memberId: string | null) {
  return useQuery({
    queryKey: ["chama", "punctuality", memberId],
    queryFn: async () => (await apiClient.get<{ member_id: string; punctuality_pct: number }>(`/chama/members/${memberId}/punctuality`)).data,
    enabled: !!memberId,
  });
}

export function useContributions(memberId: string | null) {
  return useQuery({
    queryKey: ["chama", "contributions", memberId],
    queryFn: async () =>
      (await apiClient.get<Page<Contribution>>(`/chama/members/${memberId}/contributions`, { params: { limit: 200 } })).data.items,
    enabled: !!memberId,
  });
}

export function usePayouts(chamaId: string | null) {
  return useQuery({
    queryKey: ["chama", "payouts", chamaId],
    queryFn: async () => (await apiClient.get<Page<Payout>>(`/chama/groups/${chamaId}/payouts`, { params: { limit: 200 } })).data.items,
    enabled: !!chamaId,
  });
}

export function useCreateChama() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { group_name: string; contribution_cycle: string; cycle_amount: string }) =>
      (await apiClient.post<ChamaGroup>("/chama/groups", input)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["chama", "groups"] }),
  });
}

export function useAddMember(chamaId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { user_id: string; member_role?: string }) =>
      (await apiClient.post<ChamaMember>(`/chama/groups/${chamaId}/members`, input)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["chama", "members", chamaId] }),
  });
}

export function useRecordContribution() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { member_id: string; cycle_due_date: string; amount_due: string; amount_paid: string }) =>
      (await apiClient.post<Contribution>("/chama/contributions", input)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chama", "punctuality"] });
    },
  });
}
