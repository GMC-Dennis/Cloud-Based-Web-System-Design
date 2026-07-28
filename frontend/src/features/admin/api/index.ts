import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api-client";
import type { Page } from "@/lib/pagination";
import type { AdminUser, AuditAction, AuditLogEntry, Role } from "@/features/admin/types";

export function useUsers(params: { limit?: number; offset?: number; role?: Role; includeInactive?: boolean } = {}) {
  const { limit = 50, offset = 0, role, includeInactive = false } = params;
  return useQuery({
    queryKey: ["admin", "users", limit, offset, role, includeInactive],
    queryFn: async () =>
      (
        await apiClient.get<Page<AdminUser>>("/admin/users", {
          params: { limit, offset, role, include_inactive: includeInactive },
        })
      ).data,
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { phone_number: string; full_name: string; role: Role }) =>
      (await apiClient.post<AdminUser>("/admin/users", input)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ userId, ...input }: { userId: string; full_name?: string; role?: Role }) =>
      (await apiClient.patch<AdminUser>(`/admin/users/${userId}`, input)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
  });
}

export function useDeactivateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (userId: string) => (await apiClient.post(`/admin/users/${userId}/deactivate`)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
  });
}

export function useReactivateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (userId: string) => (await apiClient.post(`/admin/users/${userId}/reactivate`)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
  });
}

export function useAuditLog(
  params: { limit?: number; offset?: number; action?: AuditAction; targetUserId?: string } = {}
) {
  const { limit = 50, offset = 0, action, targetUserId } = params;
  return useQuery({
    queryKey: ["admin", "audit-log", limit, offset, action, targetUserId],
    queryFn: async () =>
      (
        await apiClient.get<Page<AuditLogEntry>>("/admin/audit-log", {
          params: { limit, offset, action, target_user_id: targetUserId },
        })
      ).data,
  });
}
