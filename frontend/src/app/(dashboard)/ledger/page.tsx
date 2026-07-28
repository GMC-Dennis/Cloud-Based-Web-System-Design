import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { ProductPanel } from "@/features/duka-ledger/components/ProductPanel";
import { TransactionForm } from "@/features/duka-ledger/components/TransactionForm";
import { TransactionTable } from "@/features/duka-ledger/components/TransactionTable";
import { MyLoansPanel } from "@/features/credit-scoring/components/MyLoansPanel";
import { MyScorePanel } from "@/features/credit-scoring/components/MyScorePanel";

export default function LedgerPage() {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <Card className="lg:col-span-1">
        <CardHeader>
          <CardTitle>Record transaction</CardTitle>
        </CardHeader>
        <TransactionForm />
      </Card>

      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>Recent transactions</CardTitle>
        </CardHeader>
        <TransactionTable />
      </Card>

      <Card className="lg:col-span-3">
        <CardHeader>
          <CardTitle>Products & inventory</CardTitle>
        </CardHeader>
        <ProductPanel />
      </Card>

      <Card className="lg:col-span-3">
        <CardHeader>
          <CardTitle>Your credit score</CardTitle>
        </CardHeader>
        <MyScorePanel />
      </Card>

      <Card className="lg:col-span-3">
        <CardHeader>
          <CardTitle>Your loans</CardTitle>
        </CardHeader>
        <MyLoansPanel />
      </Card>
    </div>
  );
}
