import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api-client";
import type { Product, Transaction } from "@/features/duka-ledger/types";

export function useTransactions() {
  return useQuery({
    queryKey: ["ledger", "transactions"],
    queryFn: async () => (await apiClient.get<Transaction[]>("/ledger/transactions")).data,
  });
}

export function useProducts() {
  return useQuery({
    queryKey: ["ledger", "products"],
    queryFn: async () => (await apiClient.get<Product[]>("/ledger/products")).data,
  });
}

export function useRecordSale() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { amount: string; currency?: string; is_credit?: boolean; customer_phone?: string }) =>
      (await apiClient.post<Transaction>("/ledger/transactions/sale", input)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ledger", "transactions"] }),
  });
}

export function useRecordExpense() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { amount: string; currency?: string }) =>
      (await apiClient.post<Transaction>("/ledger/transactions/expense", input)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ledger", "transactions"] }),
  });
}

export function useRecordSupplierPayment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { amount: string; currency?: string }) =>
      (await apiClient.post<Transaction>("/ledger/transactions/supplier-payment", input)).data,
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
