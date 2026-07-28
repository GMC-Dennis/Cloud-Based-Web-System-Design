export type Role = "MERCHANT" | "CHAMA_MEMBER" | "UNDERWRITER" | "ADMIN";

export interface AdminUser {
  id: string;
  phone_number: string;
  full_name: string;
  role: Role;
  created_at: string;
  deleted_at: string | null;
  created_by: string | null;
  is_active: boolean;
}

export type AuditAction = "CREATE_USER" | "UPDATE_USER" | "DEACTIVATE_USER" | "REACTIVATE_USER";

export interface AuditLogEntry {
  id: string;
  actor_user_id: string;
  actor_full_name: string | null;
  target_user_id: string | null;
  target_full_name: string | null;
  action: AuditAction;
  detail: Record<string, unknown> | null;
  created_at: string;
}
