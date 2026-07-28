"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useRecordExpense, useRecordSale, useRecordSupplierPayment } from "@/features/duka-ledger/api";

const schema = z.object({
  type: z.enum(["SALE", "EXPENSE", "SUPPLIER_PAYMENT"]),
  amount: z.string().min(1, "Required"),
  isCredit: z.boolean().optional(),
  customerPhone: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

export function TransactionForm() {
  const { register, handleSubmit, watch, reset, formState } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { type: "SALE", amount: "", isCredit: false, customerPhone: "" },
  });
  const recordSale = useRecordSale();
  const recordExpense = useRecordExpense();
  const recordSupplierPayment = useRecordSupplierPayment();

  const type = watch("type");
  const pending = recordSale.isPending || recordExpense.isPending || recordSupplierPayment.isPending;

  async function onSubmit(values: FormValues) {
    if (values.type === "SALE") {
      await recordSale.mutateAsync({ amount: values.amount, is_credit: values.isCredit, customer_phone: values.customerPhone || undefined });
    } else if (values.type === "EXPENSE") {
      await recordExpense.mutateAsync({ amount: values.amount });
    } else {
      await recordSupplierPayment.mutateAsync({ amount: values.amount });
    }
    reset({ type: values.type, amount: "", isCredit: false, customerPhone: "" });
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
