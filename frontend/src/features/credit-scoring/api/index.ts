import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api-client";
import type { Applicant, CreditScore, Loan } from "@/features/credit-scoring/types";

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

export function useApplicants() {
  return useQuery({
    queryKey: ["scoring", "applicants"],
    queryFn: async () => (await apiClient.get<Applicant[]>("/underwriter/applicants")).data,
  });
}

export function useMyLoans() {
  return useQuery({
    queryKey: ["scoring", "loans", "mine"],
    queryFn: async () => (await apiClient.get<Loan[]>("/loans/mine")).data,
  });
}

export function useCreateLoan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      // borrower_id is intentionally omittable: for ALGORITHMIC loans the
      // backend resolves the borrower from credit_score_id server-side, since
      // the anonymized underwriter_applicant_view never hands the browser a
      // raw user_id (see backend CreateLoanIn's docstring).
      borrower_id?: string;
      underwriting_method?: string;
      credit_score_id?: string;
      principal: string;
      interest_rate: string;
    }) => (await apiClient.post<Loan>("/loans", input)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scoring", "applicants"] }),
  });
}
