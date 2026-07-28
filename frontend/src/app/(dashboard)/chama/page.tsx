"use client";

import { useState } from "react";

import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { ChamaDetail } from "@/features/chama-portal/components/ChamaDetail";
import { ChamaList } from "@/features/chama-portal/components/ChamaList";

export default function ChamaPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <Card className="lg:col-span-1">
        <CardHeader>
          <CardTitle>Your chamas</CardTitle>
        </CardHeader>
        <ChamaList selectedId={selectedId} onSelect={setSelectedId} />
      </Card>

      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>Group details</CardTitle>
        </CardHeader>
        {selectedId ? <ChamaDetail chamaId={selectedId} /> : <p className="text-sm text-slate-500">Select a chama to view members and contributions.</p>}
      </Card>
    </div>
  );
}
