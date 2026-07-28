"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui/table";
import { useCreateProduct, useProducts, useRestockProduct } from "@/features/duka-ledger/api";

export function ProductPanel() {
  const { data: products, isLoading } = useProducts();
  const createProduct = useCreateProduct();
  const restock = useRestockProduct();

  const [name, setName] = useState("");
  const [unitCost, setUnitCost] = useState("");
  const [unitPrice, setUnitPrice] = useState("");
  const [restockQty, setRestockQty] = useState<Record<string, string>>({});

  async function handleCreate() {
    if (!name || !unitCost || !unitPrice) return;
    await createProduct.mutateAsync({ name, unit_cost: unitCost, unit_price: unitPrice });
    setName("");
    setUnitCost("");
    setUnitPrice("");
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-4">
        <Input placeholder="Product name" value={name} onChange={(e) => setName(e.target.value)} />
        <Input placeholder="Unit cost" inputMode="decimal" value={unitCost} onChange={(e) => setUnitCost(e.target.value)} />
        <Input placeholder="Unit price" inputMode="decimal" value={unitPrice} onChange={(e) => setUnitPrice(e.target.value)} />
        <Button onClick={handleCreate} disabled={createProduct.isPending}>
          Add product
        </Button>
      </div>

      {isLoading ? (
        <p className="text-sm text-slate-500">Loading products...</p>
      ) : !products?.length ? (
        <p className="text-sm text-slate-500">No products yet.</p>
      ) : (
        <Table>
          <Thead>
            <Tr>
              <Th>Name</Th>
              <Th>Cost</Th>
              <Th>Price</Th>
              <Th>Stock</Th>
              <Th>Restock</Th>
            </Tr>
          </Thead>
          <Tbody>
            {products.map((p) => (
              <Tr key={p.id}>
                <Td>{p.name}</Td>
                <Td>{p.unit_cost}</Td>
                <Td>{p.unit_price}</Td>
                <Td>{p.quantity_on_hand}</Td>
                <Td>
                  <div className="flex items-center gap-2">
                    <Input
                      className="h-8 w-20"
                      placeholder="Qty"
                      value={restockQty[p.id] ?? ""}
                      onChange={(e) => setRestockQty((s) => ({ ...s, [p.id]: e.target.value }))}
                    />
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={restock.isPending || !restockQty[p.id]}
                      onClick={async () => {
                        await restock.mutateAsync({ productId: p.id, quantity: Number(restockQty[p.id]) });
                        setRestockQty((s) => ({ ...s, [p.id]: "" }));
                      }}
                    >
                      Add
                    </Button>
                  </div>
                </Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      )}
    </div>
  );
}
