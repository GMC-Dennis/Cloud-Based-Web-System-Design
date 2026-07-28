import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api-client";
import { newIdempotencyKey } from "@/lib/idempotency";
import type { Page } from "@/lib/pagination";
import type { Product, Transaction } from "@/features/duka-ledger/types";

export function useTransactions(params: { limit?: number; offset?: number } = {}) {
  const { limit = 50, offset = 0 } = params;
  return useQuery({
    queryKey: ["ledger", "transactions", limit, offset],
    queryFn: async () => (await apiClient.get<Page<Transaction>>("/ledger/transactions", { params: { limit, offset } })).data,
  });
}

export function useProducts() {
  return useQuery({
    queryKey: ["ledger", "products"],
    queryFn: async () => (await apiClient.get<Page<Product>>("/ledger/products", { params: { limit: 200 } })).data.items,
  });
}

export function useRecordSale() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { amount: string; currency?: string; is_credit?: boolean; customer_phone?: string }) =>
      (
        await apiClient.post<Transaction>("/ledger/transactions/sale", input, {
          headers: { "Idempotency-Key": newIdempotencyKey() },
        })
      ).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ledger", "transactions"] }),
  });
}

export function useRecordExpense() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { amount: string; currency?: string }) =>
      (
        await apiClient.post<Transaction>("/ledger/transactions/expense", input, {
          headers: { "Idempotency-Key": newIdempotencyKey() },
        })
      ).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ledger", "transactions"] }),
  });
}

export function useRecordSupplierPayment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { amount: string; currency?: string }) =>
      (
        await apiClient.post<Transaction>("/ledger/transactions/supplier-payment", input, {
          headers: { "Idempotency-Key": newIdempotencyKey() },
        })
      ).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ledger", "transactions"] }),
  });
}

export function useCreateProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { name: string; unit_cost: string; unit_price: string; reorder_threshold?: number }) =>
      (await apiClient.post<Product>("/ledger/products", input)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ledger", "products"] }),
  });
}

export function useRestockProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ productId, quantity }: { productId: string; quantity: number }) =>
      (await apiClient.post(`/ledger/products/${productId}/restock`, { quantity })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ledger", "products"] }),
  });
}
