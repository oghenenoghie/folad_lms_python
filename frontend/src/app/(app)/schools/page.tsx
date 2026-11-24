import type { Metadata } from "next";
import Link from "next/link";
import { Building2, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { SchoolFormDialog } from "@/components/schools/school-form-dialog";
import { getSchools } from "@/lib/schools";
import { createSchool } from "@/lib/actions/schools";
import { schoolDefaults } from "@/lib/schools-forms";

export const metadata: Metadata = { title: "Schools" };

export default async function SchoolsPage() {
  const schools = await getSchools();

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Schools</h1>
          <p className="text-sm text-muted-foreground">Your organization&apos;s schools</p>
        </div>
        {schools !== null && (
          <SchoolFormDialog
            trigger={
              <Button>
                <Plus className="h-4 w-4" />
                New school
              </Button>
            }
            title="New school"
            defaultValues={schoolDefaults}
            action={createSchool}
          />
        )}
      </div>

      {schools === null ? (
        <p className="text-sm text-muted-foreground">You don&apos;t have access to schools.</p>
      ) : schools.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed py-16 text-center">
          <Building2 className="h-8 w-8 text-muted-foreground" />
          <p className="font-medium">No schools yet</p>
          <p className="text-sm text-muted-foreground">Create your organization&apos;s first school to get started.</p>
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
            {schools.map((school) => (
              <TableRow key={school.public_id}>
                <TableCell>
                  <Link href={`/schools/${school.public_id}`} className="font-medium text-primary hover:underline">
                    {school.name}
                  </Link>
                </TableCell>
                <TableCell>{school.code}</TableCell>
                <TableCell>
                  <Badge variant={school.is_active ? "default" : "secondary"}>
                    {school.is_active ? "Active" : "Inactive"}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">
                  <Button asChild variant="ghost" size="icon-sm">
                    <Link href={`/schools/${school.public_id}`}>View</Link>
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
