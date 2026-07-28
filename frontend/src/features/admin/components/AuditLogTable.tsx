"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui/table";
import { useAuditLog } from "@/features/admin/api";
import type { AuditAction } from "@/features/admin/types";

const PAGE_SIZE = 50;
const ACTION_FILTERS: (AuditAction | "ALL")[] = ["ALL", "CREATE_USER", "UPDATE_USER", "DEACTIVATE_USER", "REACTIVATE_USER"];

export function AuditLogTable() {
  const [offset, setOffset] = useState(0);
  const [actionFilter, setActionFilter] = useState<AuditAction | "ALL">("ALL");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data, isLoading } = useAuditLog({
    limit: PAGE_SIZE,
    offset,
    action: actionFilter === "ALL" ? undefined : actionFilter,
  });

  if (isLoading) return <p className="text-sm text-slate-500">Loading audit log...</p>;

  return (
    <div className="space-y-3">
      <select
        className="h-9 rounded-md border border-slate-300 bg-white px-2 text-sm"
        value={actionFilter}
        onChange={(e) => {
          setActionFilter(e.target.value as AuditAction | "ALL");
          setOffset(0);
        }}
      >
        {ACTION_FILTERS.map((a) => (
          <option key={a} value={a}>
            {a === "ALL" ? "All actions" : a}
          </option>
        ))}
      </select>

      {!data?.items.length ? (
        <p className="text-sm text-slate-500">No audit log entries match this filter.</p>
      ) : (
        <>
          <Table>
            <Thead>
              <Tr>
                <Th>When</Th>
                <Th>Actor</Th>
                <Th>Action</Th>
                <Th>Target</Th>
                <Th>Detail</Th>
              </Tr>
            </Thead>
            <Tbody>
              {data.items.map((entry) => (
                <Tr key={entry.id}>
                  <Td>{new Date(entry.created_at).toLocaleString()}</Td>
                  <Td>{entry.actor_full_name ?? entry.actor_user_id}</Td>
                  <Td>
                    <Badge tone="neutral">{entry.action}</Badge>
                  </Td>
                  <Td>{entry.target_full_name ?? entry.target_user_id ?? "—"}</Td>
                  <Td>
                    {entry.detail ? (
                      <>
                        <Button size="sm" variant="secondary" onClick={() => setExpandedId(expandedId === entry.id ? null : entry.id)}>
                          {expandedId === entry.id ? "Hide" : "View"}
                        </Button>
                        {expandedId === entry.id && (
                          <pre className="mt-2 max-w-md overflow-x-auto rounded-md bg-slate-50 p-2 text-xs text-slate-700">
                            {JSON.stringify(entry.detail, null, 2)}
                          </pre>
                        )}
                      </>
                    ) : (
                      "—"
                    )}
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>

          <div className="flex items-center justify-between text-sm text-slate-500">
            <span>
              {offset + 1}-{offset + data.items.length} of {data.total}
            </span>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}>
                Previous
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={offset + data.items.length >= data.total}
                onClick={() => setOffset((o) => o + PAGE_SIZE)}
              >
                Next
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
