import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChamaList } from "@/features/chama-portal/components/ChamaList";
import { renderWithQueryClient } from "../test-utils";

vi.mock("@/features/chama-portal/api", () => ({
  useMyChamas: () => ({
    data: [{ id: "g1", group_name: "Umoja Chama", contribution_cycle: "MONTHLY", cycle_amount: "1000", created_at: "2026-01-01T00:00:00Z" }],
    isLoading: false,
  }),
  useCreateChama: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

describe("ChamaList", () => {
  it("renders the merchant's chama groups", () => {
    renderWithQueryClient(<ChamaList selectedId={null} onSelect={() => {}} />);
    expect(screen.getByText(/Umoja Chama/)).toBeInTheDocument();
  });
});
