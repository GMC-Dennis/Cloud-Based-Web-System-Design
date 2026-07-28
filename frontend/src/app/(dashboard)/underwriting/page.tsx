import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { ApplicantTable } from "@/features/credit-scoring/components/ApplicantTable";

export default function UnderwritingPage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Applicants</CardTitle>
      </CardHeader>
      <ApplicantTable />
    </Card>
  );
}
