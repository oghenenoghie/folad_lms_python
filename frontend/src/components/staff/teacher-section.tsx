import { GraduationCap, Pencil, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TeacherFormDialog } from "@/components/staff/teacher-form-dialog";
import { DeleteConfirmButton } from "@/components/schools/delete-confirm-button";
import { getTeacherForStaff } from "@/lib/staff";
import { createTeacher, updateTeacher, deleteTeacher } from "@/lib/actions/staff";
import { teacherDefaults } from "@/lib/staff-forms";

export async function TeacherSection({ staffId }: { staffId: string }) {
  const teacher = await getTeacherForStaff(staffId);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Teacher profile</CardTitle>
        {!teacher && (
          <TeacherFormDialog
            trigger={
              <Button size="sm" variant="secondary">
                <Plus className="h-4 w-4" />
                Add teacher profile
              </Button>
            }
            title="Add teacher profile"
            defaultValues={teacherDefaults}
            action={createTeacher.bind(null, staffId)}
          />
        )}
      </CardHeader>
      <CardContent>
        {!teacher ? (
          <div className="flex flex-col items-center gap-2 py-8 text-center">
            <GraduationCap className="h-6 w-6 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">This staff member has no teacher profile.</p>
          </div>
        ) : (
          <div className="flex items-center justify-between">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-muted-foreground">Qualification</p>
                <p>{teacher.qualification || "—"}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Specialization</p>
                <p>{teacher.specialization || "—"}</p>
              </div>
            </div>
            <div className="flex gap-1">
              <TeacherFormDialog
                trigger={
                  <Button variant="ghost" size="icon-sm">
                    <Pencil className="h-4 w-4" />
                  </Button>
                }
                title="Edit teacher profile"
                defaultValues={{ qualification: teacher.qualification, specialization: teacher.specialization }}
                action={updateTeacher.bind(null, staffId, teacher.public_id)}
              />
              <DeleteConfirmButton
                description="Remove this teacher profile? This cannot be undone."
                action={deleteTeacher.bind(null, staffId, teacher.public_id)}
              />
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
