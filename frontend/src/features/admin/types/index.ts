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
