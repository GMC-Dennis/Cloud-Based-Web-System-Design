"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui/table";
import { useDeactivateUser, useReactivateUser, useUpdateUser, useUsers } from "@/features/admin/api";
import type { AdminUser, Role } from "@/features/admin/types";

const PAGE_SIZE = 50;
const ROLE_FILTERS: (Role | "ALL")[] = ["ALL", "MERCHANT", "CHAMA_MEMBER", "UNDERWRITER", "ADMIN"];

export function UserTable() {
  const [offset, setOffset] = useState(0);
  const [roleFilter, setRoleFilter] = useState<Role | "ALL">("ALL");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editRole, setEditRole] = useState<Role>("MERCHANT");

  const { data, isLoading } = useUsers({
    limit: PAGE_SIZE,
    offset,
    role: roleFilter === "ALL" ? undefined : roleFilter,
    includeInactive,
  });
  const updateUser = useUpdateUser();
  const deactivateUser = useDeactivateUser();
  const reactivateUser = useReactivateUser();

  function startEdit(user: AdminUser) {
    setEditingId(user.id);
    setEditName(user.full_name);
    setEditRole(user.role);
  }

  if (isLoading) return <p className="text-sm text-slate-500">Loading users...</p>;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <select
          className="h-9 rounded-md border border-slate-300 bg-white px-2 text-sm"
          value={roleFilter}
          onChange={(e) => {
            setRoleFilter(e.target.value as Role | "ALL");
            setOffset(0);
          }}
        >
          {ROLE_FILTERS.map((r) => (
            <option key={r} value={r}>
              {r === "ALL" ? "All roles" : r}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={includeInactive}
            onChange={(e) => {
              setIncludeInactive(e.target.checked);
              setOffset(0);
            }}
          />
          Show deactivated
        </label>
      </div>

      {!data?.items.length ? (
        <p className="text-sm text-slate-500">No users match this filter.</p>
      ) : (
        <>
          <Table>
            <Thead>
              <Tr>
                <Th>Name</Th>
                <Th>Phone</Th>
                <Th>Role</Th>
                <Th>Status</Th>
                <Th>Actions</Th>
              </Tr>
            </Thead>
            <Tbody>
              {data.items.map((u) => (
                <Tr key={u.id}>
                  {editingId === u.id ? (
                    <>
                      <Td>
                        <Input className="h-8" value={editName} onChange={(e) => setEditName(e.target.value)} />
                      </Td>
                      <Td>{u.phone_number}</Td>
                      <Td>
                        <select
                          className="h-8 rounded-md border border-slate-300 bg-white px-2 text-sm"
                          value={editRole}
                          onChange={(e) => setEditRole(e.target.value as Role)}
                        >
                          {(["MERCHANT", "CHAMA_MEMBER", "UNDERWRITER", "ADMIN"] as Role[]).map((r) => (
                            <option key={r} value={r}>
                              {r}
                            </option>
                          ))}
                        </select>
                      </Td>
                      <Td>
                        <Badge tone={u.is_active ? "success" : "danger"}>{u.is_active ? "Active" : "Deactivated"}</Badge>
                      </Td>
                      <Td>
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            disabled={updateUser.isPending}
                            onClick={async () => {
                              await updateUser.mutateAsync({ userId: u.id, full_name: editName, role: editRole });
                              setEditingId(null);
                            }}
                          >
                            Save
                          </Button>
                          <Button size="sm" variant="secondary" onClick={() => setEditingId(null)}>
                            Cancel
                          </Button>
                        </div>
                      </Td>
                    </>
                  ) : (
                    <>
                      <Td>{u.full_name}</Td>
                      <Td>{u.phone_number}</Td>
                      <Td>{u.role}</Td>
                      <Td>
                        <Badge tone={u.is_active ? "success" : "danger"}>{u.is_active ? "Active" : "Deactivated"}</Badge>
                      </Td>
                      <Td>
                        <div className="flex gap-2">
                          <Button size="sm" variant="secondary" onClick={() => startEdit(u)}>
                            Edit
                          </Button>
                          {u.is_active ? (
                            <Button
                              size="sm"
                              variant="danger"
                              disabled={deactivateUser.isPending}
                              onClick={() => deactivateUser.mutate(u.id)}
                            >
                              Deactivate
                            </Button>
                          ) : (
                            <Button size="sm" disabled={reactivateUser.isPending} onClick={() => reactivateUser.mutate(u.id)}>
                              Reactivate
                            </Button>
                          )}
                        </div>
                      </Td>
                    </>
                  )}
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
