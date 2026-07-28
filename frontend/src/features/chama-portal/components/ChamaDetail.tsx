"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui/table";
import { useAddMember, useChamaMembers, usePunctuality, useRecordContribution } from "@/features/chama-portal/api";

export function ChamaDetail({ chamaId }: { chamaId: string }) {
  const { data: members, isLoading } = useChamaMembers(chamaId);
  const addMember = useAddMember(chamaId);
  const recordContribution = useRecordContribution();

  const [newMemberUserId, setNewMemberUserId] = useState("");
  const [selectedMemberId, setSelectedMemberId] = useState<string | null>(null);
  const [dueDate, setDueDate] = useState("");
  const [amountDue, setAmountDue] = useState("");
  const [amountPaid, setAmountPaid] = useState("");
  const [contributionError, setContributionError] = useState<string | null>(null);

  const { data: punctuality } = usePunctuality(selectedMemberId);

  return (
    <div className="space-y-6">
      <div className="flex items-end gap-2">
        <Input placeholder="User ID to add" value={newMemberUserId} onChange={(e) => setNewMemberUserId(e.target.value)} />
        <Button
          onClick={async () => {
            if (!newMemberUserId) return;
            await addMember.mutateAsync({ user_id: newMemberUserId });
            setNewMemberUserId("");
          }}
          disabled={addMember.isPending}
        >
          Add member
        </Button>
      </div>

      {isLoading ? (
        <p className="text-sm text-slate-500">Loading members...</p>
      ) : (
        <Table>
          <Thead>
            <Tr>
              <Th>User</Th>
              <Th>Role</Th>
              <Th>Joined</Th>
              <Th>Punctuality</Th>
            </Tr>
          </Thead>
          <Tbody>
            {members?.map((m) => (
              <Tr key={m.id} onClick={() => setSelectedMemberId(m.id)} className="cursor-pointer">
                <Td>{m.user_id}</Td>
                <Td>{m.member_role}</Td>
                <Td>{new Date(m.joined_at).toLocaleDateString()}</Td>
                <Td>{selectedMemberId === m.id && punctuality ? <Badge tone="success">{punctuality.punctuality_pct.toFixed(0)}%</Badge> : "-"}</Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      )}

      {selectedMemberId && (
        <div className="space-y-2 rounded-md border border-slate-200 p-3">
          <p className="text-sm font-medium text-slate-700">Record contribution for selected member</p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-4">
            <Input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
            <Input placeholder="Amount due" inputMode="decimal" value={amountDue} onChange={(e) => setAmountDue(e.target.value)} />
            <Input placeholder="Amount paid" inputMode="decimal" value={amountPaid} onChange={(e) => setAmountPaid(e.target.value)} />
            <Button
              disabled={recordContribution.isPending || !dueDate || !amountDue || !amountPaid}
              onClick={async () => {
                setContributionError(null);
                try {
                  await recordContribution.mutateAsync({ member_id: selectedMemberId, cycle_due_date: dueDate, amount_due: amountDue, amount_paid: amountPaid });
                  setDueDate("");
                  setAmountDue("");
                  setAmountPaid("");
                } catch (err: unknown) {
                  const status = (err as { response?: { status?: number } }).response?.status;
                  setContributionError(
                    status === 403
                      ? "Only this chama's chairperson, treasurer, or secretary can record a contribution -- and not for their own."
                      : "Could not record the contribution.",
                  );
                }
              }}
            >
              Record
            </Button>
          </div>
          {contributionError && <p className="text-sm text-red-600">{contributionError}</p>}
        </div>
      )}
    </div>
  );
}
