"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCreateChama, useMyChamas } from "@/features/chama-portal/api";

export function ChamaList({ selectedId, onSelect }: { selectedId: string | null; onSelect: (id: string) => void }) {
  const { data: groups, isLoading } = useMyChamas();
  const createChama = useCreateChama();

  const [name, setName] = useState("");
  const [cycle, setCycle] = useState<"WEEKLY" | "MONTHLY">("MONTHLY");
  const [amount, setAmount] = useState("");

  async function handleCreate() {
    if (!name || !amount) return;
    const group = await createChama.mutateAsync({ group_name: name, contribution_cycle: cycle, cycle_amount: amount });
    setName("");
    setAmount("");
    onSelect(group.id);
  }

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        <Input placeholder="Group name" value={name} onChange={(e) => setName(e.target.value)} />
        <select className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm" value={cycle} onChange={(e) => setCycle(e.target.value as "WEEKLY" | "MONTHLY")}>
          <option value="WEEKLY">Weekly</option>
          <option value="MONTHLY">Monthly</option>
        </select>
        <Input placeholder="Cycle amount (KES)" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
        <Button className="w-full" onClick={handleCreate} disabled={createChama.isPending}>
          Create chama
        </Button>
      </div>

      {isLoading ? (
        <p className="text-sm text-slate-500">Loading...</p>
      ) : (
        <ul className="space-y-1">
          {groups?.map((g) => (
            <li key={g.id}>
              <button
                onClick={() => onSelect(g.id)}
                className={`w-full rounded-md px-3 py-2 text-left text-sm ${g.id === selectedId ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}
              >
                {g.group_name} · {g.contribution_cycle}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
