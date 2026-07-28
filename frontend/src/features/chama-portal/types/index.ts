export interface ChamaGroup {
  id: string;
  group_name: string;
  contribution_cycle: "WEEKLY" | "MONTHLY";
  cycle_amount: string;
  created_at: string;
}

export interface ChamaMember {
  id: string;
  chama_id: string;
  user_id: string;
  member_role: string;
  joined_at: string;
}

export interface Contribution {
  id: string;
  chama_id: string;
  member_id: string;
  cycle_due_date: string;
  amount_due: string;
  amount_paid: string;
  paid_at: string | null;
  is_on_time: boolean | null;
}

export interface Payout {
  id: string;
  chama_id: string;
  recipient_member_id: string;
  payout_amount: string;
  scheduled_date: string;
  paid_out_at: string | null;
}
