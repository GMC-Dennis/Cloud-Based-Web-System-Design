"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useProducts, useRecordExpense, useRecordSale, useRecordSupplierPayment } from "@/features/duka-ledger/api";

const schema = z.object({
  type: z.enum(["SALE", "EXPENSE", "SUPPLIER_PAYMENT"]),
  amount: z.string().min(1, "Required"),
  isCredit: z.boolean().optional(),
  customerPhone: z.string().optional(),
  productId: z.string().optional(),
  quantity: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

export function TransactionForm() {
  const { register, handleSubmit, watch, reset, formState, setError, clearErrors } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { type: "SALE", amount: "", isCredit: false, customerPhone: "", productId: "", quantity: "1" },
  });
  const { data: products } = useProducts();
  const recordSale = useRecordSale();
  const recordExpense = useRecordExpense();
  const recordSupplierPayment = useRecordSupplierPayment();

  const type = watch("type");
  const pending = recordSale.isPending || recordExpense.isPending || recordSupplierPayment.isPending;

  async function onSubmit(values: FormValues) {
    if (values.type === "SALE") {
      // Required server-side too: a sale must reference a real product so
      // revenue is tied to an actual inventory movement, not a bare number.
      if (!values.productId) {
        setError("productId", { message: "Pick which product this sale is for" });
        return;
      }
      clearErrors("productId");
      await recordSale.mutateAsync({
        amount: values.amount,
        is_credit: values.isCredit,
        customer_phone: values.customerPhone || undefined,
        line_items: [{ product_id: values.productId, quantity: Number(values.quantity) || 1 }],
      });
    } else if (values.type === "EXPENSE") {
      await recordExpense.mutateAsync({ amount: values.amount });
    } else {
      await recordSupplierPayment.mutateAsync({ amount: values.amount });
    }
    reset({ type: values.type, amount: "", isCredit: false, customerPhone: "", productId: "", quantity: "1" });
  }

  return (
    <form className="space-y-3" onSubmit={handleSubmit(onSubmit)}>
      <select className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm" {...register("type")}>
        <option value="SALE">Sale</option>
        <option value="EXPENSE">Expense</option>
        <option value="SUPPLIER_PAYMENT">Supplier payment</option>
      </select>
      <Input placeholder="Amount (KES)" inputMode="decimal" {...register("amount")} />
      {formState.errors.amount && <p className="text-sm text-red-600">{formState.errors.amount.message}</p>}

      {type === "SALE" && (
        <>
          <select className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm" {...register("productId")}>
            <option value="">Which product?</option>
            {products?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.quantity_on_hand} in stock)
              </option>
            ))}
          </select>
          {formState.errors.productId && <p className="text-sm text-red-600">{formState.errors.productId.message}</p>}
          {!products?.length && <p className="text-sm text-amber-600">Add a product below before recording a sale.</p>}
          <Input placeholder="Quantity sold" inputMode="numeric" {...register("quantity")} />
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input type="checkbox" {...register("isCredit")} /> Sold on credit
          </label>
          <Input placeholder="Customer phone (optional)" {...register("customerPhone")} />
        </>
      )}

      <Button type="submit" disabled={pending} className="w-full">
        Record
      </Button>
    </form>
  );
}
