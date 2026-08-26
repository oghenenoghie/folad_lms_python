import type { Metadata } from "next";
import Link from "next/link";
import { Briefcase, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { StaffCreateFormDialog } from "@/components/staff/staff-form-dialog";
import { getStaffList } from "@/lib/staff";
import { getSchools } from "@/lib/schools";
import { createStaff } from "@/lib/actions/staff";
import { staffCreateDefaults, employmentStatusLabel } from "@/lib/staff-forms";

export const metadata: Metadata = { title: "Staff" };

export default async function StaffPage() {
  const [staff, schools] = await Promise.all([getStaffList(), getSchools()]);
  const schoolNameById = new Map((schools ?? []).map((school) => [school.public_id, school.name]));
  const schoolOptions = (schools ?? []).map((school) => ({ value: school.public_id, label: school.name }));

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Staff</h1>
          <p className="text-sm text-muted-foreground">Employees across your organization&apos;s schools</p>
        </div>
        {staff !== null && schoolOptions.length > 0 && (
          <StaffCreateFormDialog
            trigger={
              <Button>
                <Plus className="h-4 w-4" />
                New staff
              </Button>
            }
            title="New staff"
            defaultValues={staffCreateDefaults}
            schoolOptions={schoolOptions}
            action={createStaff}
          />
        )}
      </div>

      {staff === null ? (
        <p className="text-sm text-muted-foreground">You don&apos;t have access to staff.</p>
      ) : staff.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed py-16 text-center">
          <Briefcase className="h-8 w-8 text-muted-foreground" />
          <p className="font-medium">No staff yet</p>
          <p className="text-sm text-muted-foreground">
            {schoolOptions.length === 0
              ? "Create a school first, then add staff to it."
              : "Add your first staff member to get started."}
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>School</TableHead>
              <TableHead>Position</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-1" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {staff.map((member) => (
              <TableRow key={member.public_id}>
                <TableCell>
                  <Link href={`/staff/${member.public_id}`} className="font-medium text-primary hover:underline">
                    {member.first_name} {member.last_name}
                  </Link>
                  <p className="text-xs text-muted-foreground">{member.employee_number}</p>
                </TableCell>
                <TableCell>{schoolNameById.get(member.school) ?? "—"}</TableCell>
                <TableCell>{member.position}</TableCell>
                <TableCell>
                  <Badge variant={member.employment_status === "active" ? "default" : "secondary"}>
                    {employmentStatusLabel(member.employment_status)}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">
                  <Button asChild variant="ghost" size="icon-sm">
                    <Link href={`/staff/${member.public_id}`}>View</Link>
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
