import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import type { Student } from "@/lib/dashboard";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  Active: "default",
  Inactive: "secondary",
  Graduated: "outline",
  Withdrawn: "destructive",
  Suspended: "destructive",
};

const STATUS_LABELS: Record<string, string> = {
  active: "Active",
  inactive: "Inactive",
  graduated: "Graduated",
  withdrawn: "Withdrawn",
  suspended: "Suspended",
};

export function StudentsTable({ students }: { students: Student[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Admission #</TableHead>
          <TableHead>Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {students.map((student) => {
          const label = STATUS_LABELS[student.enrollment_status] ?? student.enrollment_status;
          return (
            <TableRow key={student.public_id}>
              <TableCell className="font-medium">
                {student.first_name} {student.last_name}
              </TableCell>
              <TableCell>{student.admission_number}</TableCell>
              <TableCell>
                <Badge variant={STATUS_VARIANT[label] ?? "secondary"}>{label}</Badge>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
