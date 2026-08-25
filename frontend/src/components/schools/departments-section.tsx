import { Building2, Pencil, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DepartmentFormDialog } from "@/components/schools/department-form-dialog";
import { DeleteConfirmButton } from "@/components/schools/delete-confirm-button";
import { getDepartments } from "@/lib/schools";
import { createDepartment, updateDepartment, deleteDepartment } from "@/lib/actions/schools";
import { departmentDefaults } from "@/lib/schools-forms";

export async function DepartmentsSection({ schoolId }: { schoolId: string }) {
  const departments = await getDepartments(schoolId);
  if (departments === null) return null;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Departments</CardTitle>
        <DepartmentFormDialog
          trigger={
            <Button size="sm" variant="secondary">
              <Plus className="h-4 w-4" />
              New department
            </Button>
          }
          title="New department"
          defaultValues={departmentDefaults}
          action={createDepartment.bind(null, schoolId)}
        />
      </CardHeader>
      <CardContent>
        {departments.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-8 text-center">
            <Building2 className="h-6 w-6 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">No departments yet</p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Code</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-1" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {departments.map((department) => (
                <TableRow key={department.public_id}>
                  <TableCell>{department.name}</TableCell>
                  <TableCell>{department.code}</TableCell>
                  <TableCell>
                    <Badge variant={department.is_active ? "default" : "secondary"}>
                      {department.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </TableCell>
                  <TableCell className="flex justify-end gap-1">
                    <DepartmentFormDialog
                      trigger={
                        <Button variant="ghost" size="icon-sm">
                          <Pencil className="h-4 w-4" />
                        </Button>
                      }
                      title="Edit department"
                      defaultValues={{
                        name: department.name,
                        code: department.code,
                        description: department.description,
                        is_active: department.is_active,
                      }}
                      action={updateDepartment.bind(null, schoolId, department.public_id)}
                    />
                    <DeleteConfirmButton
                      description={`Delete department ${department.name}?`}
                      action={deleteDepartment.bind(null, schoolId, department.public_id)}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
