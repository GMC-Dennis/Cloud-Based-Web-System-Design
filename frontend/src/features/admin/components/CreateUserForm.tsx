"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCreateUser } from "@/features/admin/api";
import type { Role } from "@/features/admin/types";

const ROLES: Role[] = ["MERCHANT", "CHAMA_MEMBER", "UNDERWRITER", "ADMIN"];

export function CreateUserForm() {
  const createUser = useCreateUser();
  const [phone, setPhone] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<Role>("UNDERWRITER");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    setError(null);
    if (!phone || !fullName) return;
    try {
      await createUser.mutateAsync({ phone_number: phone, full_name: fullName, role });
      setPhone("");
      setFullName("");
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } }).response?.status;
      setError(status === 409 ? "That phone number is already registered." : "Could not create the account.");
    }
  }

  return (
    <div className="space-y-2">
      <p className="text-sm text-slate-500">
        This is the only way to onboard an <strong>UNDERWRITER</strong> or <strong>ADMIN</strong> account -- those roles can&apos;t be
        self-registered. The account can log in normally right after creation; no invite step is needed.
      </p>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-4">
        <Input placeholder="+254712345678" value={phone} onChange={(e) => setPhone(e.target.value)} />
        <Input placeholder="Full name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
        <select className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm" value={role} onChange={(e) => setRole(e.target.value as Role)}>
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <Button onClick={handleSubmit} disabled={createUser.isPending || !phone || !fullName}>
          Create account
        </Button>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
