import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { CreateUserForm } from "@/features/admin/components/CreateUserForm";
import { UserTable } from "@/features/admin/components/UserTable";

export default function AdminPage() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Onboard an underwriter or admin</CardTitle>
        </CardHeader>
        <CreateUserForm />
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Users</CardTitle>
        </CardHeader>
        <UserTable />
      </Card>
    </div>
  );
}
