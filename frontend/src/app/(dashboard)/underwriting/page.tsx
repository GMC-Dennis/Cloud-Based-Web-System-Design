import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { ApplicantTable } from "@/features/credit-scoring/components/ApplicantTable";
import { ManualLoanPanel } from "@/features/credit-scoring/components/ManualLoanPanel";

export default function UnderwritingPage() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Applicants</CardTitle>
        </CardHeader>
        <ApplicantTable />
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Manual underwriting</CardTitle>
        </CardHeader>
        <ManualLoanPanel />
      </Card>
    </div>
  );
}
