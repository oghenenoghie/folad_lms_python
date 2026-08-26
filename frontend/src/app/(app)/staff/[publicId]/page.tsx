import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { StaffEditFormDialog } from "@/components/staff/staff-form-dialog";
import { DeleteConfirmButton } from "@/components/schools/delete-confirm-button";
import { TeacherSection } from "@/components/staff/teacher-section";
import { getStaffMember } from "@/lib/staff";
import { getSchool, getDepartments } from "@/lib/schools";
import { updateStaff, deleteStaff } from "@/lib/actions/staff";
import { employmentStatusLabel, NO_DEPARTMENT } from "@/lib/staff-forms";

export async function generateMetadata({ params }: { params: Promise<{ publicId: string }> }): Promise<Metadata> {
  const { publicId } = await params;
  const staff = await getStaffMember(publicId);
  return { title: staff ? `${staff.first_name} ${staff.last_name}` : "Staff" };
}

export default async function StaffDetailPage({ params }: { params: Promise<{ publicId: string }> }) {
  const { publicId } = await params;
  const staff = await getStaffMember(publicId);
  if (!staff) notFound();

  const [school, departments] = await Promise.all([getSchool(staff.school), getDepartments(staff.school)]);
  const departmentOptions = [
    { value: NO_DEPARTMENT, label: "— None —" },
    ...(departments ?? []).map((department) => ({ value: department.public_id, label: department.name })),
  ];
  const departmentName = departments?.find((department) => department.public_id === staff.department)?.name;

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold">
            {staff.first_name} {staff.last_name}
          </h1>
          <p className="text-sm text-muted-foreground">
            {staff.employee_number} · {school?.name ?? "Unknown school"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StaffEditFormDialog
            trigger={
              <Button variant="secondary">
                <Pencil className="h-4 w-4" />
                Edit
              </Button>
            }
            title="Edit staff"
            defaultValues={{
              employee_number: staff.employee_number,
              first_name: staff.first_name,
              last_name: staff.last_name,
              position: staff.position,
              employment_status: staff.employment_status,
              date_joined: staff.date_joined,
              department: staff.department ?? NO_DEPARTMENT,
            }}
            departmentOptions={departmentOptions}
            action={updateStaff.bind(null, staff.public_id)}
          />
          <DeleteConfirmButton
            description={`Delete ${staff.first_name} ${staff.last_name}? This cannot be undone.`}
            action={deleteStaff.bind(null, staff.public_id)}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 rounded-lg border p-4 text-sm sm:grid-cols-4">
        <div>
          <p className="text-muted-foreground">Position</p>
          <p>{staff.position}</p>
        </div>
        <div>
          <p className="text-muted-foreground">Department</p>
          <p>{departmentName ?? "—"}</p>
        </div>
        <div>
          <p className="text-muted-foreground">Status</p>
          <Badge variant={staff.employment_status === "active" ? "default" : "secondary"}>
            {employmentStatusLabel(staff.employment_status)}
          </Badge>
        </div>
        <div>
          <p className="text-muted-foreground">Date joined</p>
          <p>{staff.date_joined}</p>
        </div>
      </div>

      <TeacherSection staffId={staff.public_id} />
    </div>
  );
}
