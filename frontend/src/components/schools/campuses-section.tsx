import { Building2, Pencil, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CampusFormDialog } from "@/components/schools/campus-form-dialog";
import { DeleteConfirmButton } from "@/components/schools/delete-confirm-button";
import { getCampuses } from "@/lib/schools";
import { createCampus, updateCampus, deleteCampus } from "@/lib/actions/schools";
import { campusDefaults } from "@/lib/schools-forms";

export async function CampusesSection({ schoolId }: { schoolId: string }) {
  const campuses = await getCampuses(schoolId);
  if (campuses === null) return null;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Campuses</CardTitle>
        <CampusFormDialog
          trigger={
            <Button size="sm" variant="secondary">
              <Plus className="h-4 w-4" />
              New campus
            </Button>
          }
          title="New campus"
          defaultValues={campusDefaults}
          action={createCampus.bind(null, schoolId)}
        />
      </CardHeader>
      <CardContent>
        {campuses.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-8 text-center">
            <Building2 className="h-6 w-6 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">No campuses yet</p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Code</TableHead>
                <TableHead>Main</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-1" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {campuses.map((campus) => (
                <TableRow key={campus.public_id}>
                  <TableCell>{campus.name}</TableCell>
                  <TableCell>{campus.code}</TableCell>
                  <TableCell>{campus.is_main && <Badge variant="outline">Main</Badge>}</TableCell>
                  <TableCell>
                    <Badge variant={campus.is_active ? "default" : "secondary"}>
                      {campus.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </TableCell>
                  <TableCell className="flex justify-end gap-1">
                    <CampusFormDialog
                      trigger={
                        <Button variant="ghost" size="icon-sm">
                          <Pencil className="h-4 w-4" />
                        </Button>
                      }
                      title="Edit campus"
                      defaultValues={{
                        name: campus.name,
                        code: campus.code,
                        address: campus.address,
                        is_main: campus.is_main,
                        is_active: campus.is_active,
                      }}
                      action={updateCampus.bind(null, schoolId, campus.public_id)}
                    />
                    <DeleteConfirmButton
                      description={`Delete campus ${campus.name}? This cannot be undone.`}
                      action={deleteCampus.bind(null, schoolId, campus.public_id)}
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
