export interface CreditScore {
  id: string;
  user_id: string;
  credit_score: number;
  recommended_limit: string;
  risk_tier: "LOW" | "MEDIUM" | "HIGH";
  model_version: string;
  shap_explanation: Record<string, number>;
  evaluated_at: string;
}

export interface Applicant {
  credit_score_id: string;
  loan_id: string | null;
  credit_score: number;
  risk_tier: "LOW" | "MEDIUM" | "HIGH";
  recommended_limit: string;
  shap_explanation: Record<string, number>;
  applicant_name: string | null;
  applicant_phone: string | null;
  status: string | null;
}

export interface Loan {
  id: string;
  borrower_id: string;
  credit_score_id: string | null;
  underwriting_method: "ALGORITHMIC" | "MANUAL" | "OVERRIDE";
  override_reason: string | null;
  principal: string;
  interest_rate: string;
  status: string;
  disbursed_at: string | null;
  due_date: string | null;
  created_at: string;
}

export interface Repayment {
  id: string;
  loan_id: string;
  amount: string;
  paid_at: string;
}
