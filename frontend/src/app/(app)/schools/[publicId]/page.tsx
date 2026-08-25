import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SchoolFormDialog } from "@/components/schools/school-form-dialog";
import { DeleteConfirmButton } from "@/components/schools/delete-confirm-button";
import { CampusesSection } from "@/components/schools/campuses-section";
import { AcademicYearsSection } from "@/components/schools/academic-years-section";
import { DepartmentsSection } from "@/components/schools/departments-section";
import { getSchool } from "@/lib/schools";
import { updateSchool, deleteSchool } from "@/lib/actions/schools";

export async function generateMetadata({ params }: { params: Promise<{ publicId: string }> }): Promise<Metadata> {
  const { publicId } = await params;
  const school = await getSchool(publicId);
  return { title: school?.name ?? "School" };
}

export default async function SchoolDetailPage({ params }: { params: Promise<{ publicId: string }> }) {
  const { publicId } = await params;
  const school = await getSchool(publicId);
  if (!school) notFound();

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold">{school.name}</h1>
          <p className="text-sm text-muted-foreground">
            {school.code}
            {!school.is_active && " · Inactive"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <SchoolFormDialog
            trigger={
              <Button variant="secondary">
                <Pencil className="h-4 w-4" />
                Edit
              </Button>
            }
            title="Edit school"
            defaultValues={{
              name: school.name,
              code: school.code,
              address: school.address,
              phone: school.phone,
              email: school.email,
              default_grading_scheme: school.default_grading_scheme,
              is_active: school.is_active,
            }}
            action={updateSchool.bind(null, school.public_id)}
          />
          <DeleteConfirmButton
            description={`Delete ${school.name}? This cannot be undone.`}
            action={deleteSchool.bind(null, school.public_id)}
          />
        </div>
      </div>

      {(school.address || school.phone || school.email) && (
        <div className="grid grid-cols-1 gap-3 rounded-lg border p-4 text-sm sm:grid-cols-3">
          <div>
            <p className="text-muted-foreground">Address</p>
            <p>{school.address || "—"}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Phone</p>
            <p>{school.phone || "—"}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Email</p>
            <p>{school.email || "—"}</p>
          </div>
        </div>
      )}

      <CampusesSection schoolId={school.public_id} />
      <AcademicYearsSection schoolId={school.public_id} />
      <DepartmentsSection schoolId={school.public_id} />
    </div>
  );
}
