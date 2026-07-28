import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TransactionTable } from "@/features/duka-ledger/components/TransactionTable";
import { renderWithQueryClient } from "../test-utils";

vi.mock("@/features/duka-ledger/api", () => ({
  useTransactions: () => ({
    data: [
      {
        id: "t1",
        merchant_id: "m1",
        sequence_no: 1,
        amount: "150.00",
        currency: "KES",
        transaction_type: "SALE",
        is_credit: false,
        customer_phone: null,
        record_hash: "abc",
        created_at: "2026-07-01T00:00:00Z",
      },
    ],
    isLoading: false,
    error: null,
  }),
}));

describe("TransactionTable", () => {
  it("renders transaction rows from the API", () => {
    renderWithQueryClient(<TransactionTable />);
    expect(screen.getByText("SALE")).toBeInTheDocument();
    expect(screen.getByText(/150.00/)).toBeInTheDocument();
  });
});
