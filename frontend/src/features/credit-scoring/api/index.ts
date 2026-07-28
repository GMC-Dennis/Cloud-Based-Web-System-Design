import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api-client";
import type { Page } from "@/lib/pagination";
import type { Applicant, BorrowerSearchResult, CreditScore, Loan, Repayment } from "@/features/credit-scoring/types";

export function useLatestScore(userId: string | null) {
  return useQuery({
    queryKey: ["scoring", "latest", userId],
    queryFn: async () => (await apiClient.get<CreditScore>(`/scoring/scores/${userId}/latest`)).data,
    enabled: !!userId,
    retry: false,
  });
}

export function useEvaluateMerchant() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (userId: string) => (await apiClient.post<CreditScore>(`/scoring/evaluate/${userId}`)).data,
    onSuccess: (_data, userId) => queryClient.invalidateQueries({ queryKey: ["scoring", "latest", userId] }),
  });
}

export function useApplicants(params: { limit?: number; offset?: number } = {}) {
  const { limit = 50, offset = 0 } = params;
  return useQuery({
    queryKey: ["scoring", "applicants", limit, offset],
    queryFn: async () => (await apiClient.get<Page<Applicant>>("/underwriter/applicants", { params: { limit, offset } })).data,
  });
}

export function useMyLoans() {
  return useQuery({
    queryKey: ["scoring", "loans", "mine"],
    queryFn: async () => (await apiClient.get<Page<Loan>>("/loans/mine", { params: { limit: 200 } })).data.items,
  });
}

export function useLoanRepayments(loanId: string) {
  return useQuery({
    queryKey: ["scoring", "loans", loanId, "repayments"],
    queryFn: async () => (await apiClient.get<Page<Repayment>>(`/loans/${loanId}/repayments`, { params: { limit: 200 } })).data.items,
    enabled: !!loanId,
  });
}

export function useRecordRepayment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ loanId, amount }: { loanId: string; amount: string }) =>
      (await apiClient.post<Repayment>(`/loans/${loanId}/repayments`, { amount })).data,
    onSuccess: (_data, { loanId }) => queryClient.invalidateQueries({ queryKey: ["scoring", "loans", loanId, "repayments"] }),
  });
}

export function useCreateLoan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      // borrower_id is intentionally omittable: for ALGORITHMIC loans the
      // backend resolves the borrower from credit_score_id server-side, since
      // the anonymized underwriter_applicant_view never hands the browser a
      // raw user_id (see backend CreateLoanIn's docstring). MANUAL/OVERRIDE
      // loans have no score to resolve a borrower from, so they must supply
      // borrower_id (from the borrower-search flow) and override_reason directly.
      borrower_id?: string;
      underwriting_method?: string;
      credit_score_id?: string;
      override_reason?: string;
      principal: string;
      interest_rate: string;
      due_date?: string;
    }) => (await apiClient.post<Loan>("/loans", input)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scoring", "applicants"] }),
  });
}

export function useBorrowerSearch(phone: string) {
  return useQuery({
    queryKey: ["identity", "underwriter", "borrower-search", phone],
    queryFn: async () =>
      (await apiClient.get<Page<BorrowerSearchResult>>("/underwriter/users/search", { params: { phone, limit: 20 } })).data.items,
    enabled: phone.length >= 3,
  });
}
