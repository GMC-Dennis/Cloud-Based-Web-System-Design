import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { UserTable } from "@/features/admin/components/UserTable";
import { renderWithQueryClient } from "../test-utils";

vi.mock("@/features/admin/api", () => ({
  useUsers: () => ({
    data: {
      items: [
        {
          id: "u1",
          phone_number: "+254712345678",
          full_name: "Uma Underwriter",
          role: "UNDERWRITER",
          created_at: "2026-07-01T00:00:00Z",
          deleted_at: null,
          created_by: "admin-1",
          is_active: true,
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    },
    isLoading: false,
  }),
  useUpdateUser: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeactivateUser: () => ({ mutate: vi.fn(), isPending: false }),
  useReactivateUser: () => ({ mutate: vi.fn(), isPending: false }),
}));

describe("UserTable", () => {
  it("renders users with their role and active status", () => {
    renderWithQueryClient(<UserTable />);
    expect(screen.getByText("Uma Underwriter")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "UNDERWRITER" })).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Deactivate" })).toBeInTheDocument();
  });
});
