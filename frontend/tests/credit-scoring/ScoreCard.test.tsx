import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ScoreCard } from "@/features/credit-scoring/components/ScoreCard";
import { renderWithQueryClient } from "../test-utils";

vi.mock("@/features/credit-scoring/api", () => ({
  useLatestScore: () => ({
    data: {
      id: "s1",
      user_id: "u1",
      credit_score: 742,
      recommended_limit: "15000.00",
      risk_tier: "LOW",
      model_version: "rf_v3_2026_06",
      shap_explanation: { sales_velocity: -0.02, receivables_days: 0.01, chama_punctuality: -0.03, margin_stability: -0.01 },
      evaluated_at: "2026-07-01T00:00:00Z",
    },
    isLoading: false,
    error: null,
  }),
  useEvaluateMerchant: () => ({ mutate: vi.fn(), isPending: false }),
}));

describe("ScoreCard", () => {
  it("renders the credit score, tier, and SHAP feature bars", () => {
    renderWithQueryClient(<ScoreCard userId="u1" />);
    expect(screen.getByText("742")).toBeInTheDocument();
    expect(screen.getByText("LOW")).toBeInTheDocument();
    expect(screen.getByText("sales_velocity")).toBeInTheDocument();
  });
});
