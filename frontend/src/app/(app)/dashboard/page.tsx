import type { Metadata } from "next";
import { GraduationCap, Briefcase, BookOpen, HeartHandshake } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatCard } from "@/components/dashboard/stat-card";
import { EnrollmentChart } from "@/components/dashboard/enrollment-chart";
import { StudentsTable } from "@/components/dashboard/students-table";
import { getDashboardData } from "@/lib/dashboard";

export const metadata: Metadata = { title: "Dashboard" };

export default async function DashboardPage() {
  const data = await getDashboardData();

  if (!data.hasAnyAccess) {
    return (
      <div className="mx-auto max-w-6xl space-y-6 p-6">
        <h1 className="text-xl font-semibold">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          You don&apos;t have access to any dashboard modules yet. Contact an administrator to have
          permissions granted to your account.
        </p>
      </div>
    );
  }

  const hasBreakdown = Object.keys(data.enrollmentBreakdown).length > 0;

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <h1 className="text-xl font-semibold">Dashboard</h1>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {data.studentCount !== null && (
          <StatCard label="Students" value={data.studentCount} icon={GraduationCap} />
        )}
        {data.staffCount !== null && <StatCard label="Staff" value={data.staffCount} icon={Briefcase} />}
        {data.teacherCount !== null && (
          <StatCard label="Teachers" value={data.teacherCount} icon={BookOpen} />
        )}
        {data.guardianCount !== null && (
          <StatCard label="Guardians" value={data.guardianCount} icon={HeartHandshake} />
        )}
      </div>

      {data.studentCount !== null && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {hasBreakdown && (
            <Card className="lg:col-span-1">
              <CardHeader>
                <CardTitle>Enrollment status</CardTitle>
              </CardHeader>
              <CardContent className="h-64">
                <EnrollmentChart breakdown={data.enrollmentBreakdown} />
              </CardContent>
              {data.breakdownSampleSize !== null && (
                <p className="px-6 pb-4 text-xs text-muted-foreground">
                  Based on the first {data.breakdownSampleSize} of {data.studentCount} students.
                </p>
              )}
            </Card>
          )}

          <Card className={hasBreakdown ? "lg:col-span-2" : "lg:col-span-3"}>
            <CardHeader>
              <CardTitle>Students</CardTitle>
            </CardHeader>
            <CardContent>
              {data.students.length > 0 ? (
                <>
                  <StudentsTable students={data.students} />
                  {data.studentCount !== null && data.studentCount > data.students.length && (
                    <p className="mt-3 text-xs text-muted-foreground">
                      Showing {data.students.length} of {data.studentCount} students.
                    </p>
                  )}
                </>
              ) : (
                <p className="text-sm text-muted-foreground">No students yet.</p>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
