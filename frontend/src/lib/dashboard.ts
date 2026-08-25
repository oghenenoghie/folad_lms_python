import "server-only";
import { djangoFetch } from "@/lib/session";
import type { Envelope, Paginated } from "@/lib/api-types";

export type Student = {
  public_id: string;
  admission_number: string;
  first_name: string;
  last_name: string;
  enrollment_status: string;
};

const ENROLLMENT_STATUS_LABELS: Record<string, string> = {
  active: "Active",
  inactive: "Inactive",
  graduated: "Graduated",
  withdrawn: "Withdrawn",
  suspended: "Suspended",
};

export type DashboardData = {
  studentCount: number | null;
  staffCount: number | null;
  teacherCount: number | null;
  guardianCount: number | null;
  students: Student[];
  /** Number of students the enrollment breakdown was computed from, when
   * that's fewer than studentCount (the API has no aggregate endpoint, so
   * the chart is only as complete as the page of students fetched). */
  breakdownSampleSize: number | null;
  enrollmentBreakdown: Record<string, number>;
  hasAnyAccess: boolean;
};

// Fetches counts via the page_size=1 + pagination.total_count trick rather
// than inventing a stats endpoint the JSON API doesn't have. A 403 means
// the signed-in user lacks that module's `.view` permission — the same
// real enforcement Django's own require_permission() applies — so that
// section is simply omitted, mirroring apps/web/views/dashboard.py's
// permission-driven visibility without duplicating its permission checks.
export async function getDashboardData(): Promise<DashboardData> {
  const [studentsRes, staffRes, teachersRes, guardiansRes] = await Promise.all([
    djangoFetch("/api/v1/students?page_size=100"),
    djangoFetch("/api/v1/staff?page_size=1"),
    djangoFetch("/api/v1/teachers?page_size=1"),
    djangoFetch("/api/v1/guardians?page_size=1"),
  ]);

  let studentCount: number | null = null;
  let students: Student[] = [];
  let breakdownSampleSize: number | null = null;
  const enrollmentBreakdown: Record<string, number> = {};

  if (studentsRes.ok) {
    const body: Envelope<Paginated<Student>> = await studentsRes.json();
    if (body.success && body.data) {
      studentCount = body.data.pagination.total_count;
      students = body.data.results;
      if (body.data.pagination.total_count > body.data.results.length) {
        breakdownSampleSize = body.data.results.length;
      }
      for (const student of body.data.results) {
        const label = ENROLLMENT_STATUS_LABELS[student.enrollment_status] ?? student.enrollment_status;
        enrollmentBreakdown[label] = (enrollmentBreakdown[label] ?? 0) + 1;
      }
    }
  }

  const countOnly = async (res: Response): Promise<number | null> => {
    if (!res.ok) return null;
    const body: Envelope<Paginated<unknown>> = await res.json();
    return body.success && body.data ? body.data.pagination.total_count : null;
  };

  const [staffCount, teacherCount, guardianCount] = await Promise.all([
    countOnly(staffRes),
    countOnly(teachersRes),
    countOnly(guardiansRes),
  ]);

  return {
    studentCount,
    staffCount,
    teacherCount,
    guardianCount,
    students: students.slice(0, 5),
    breakdownSampleSize,
    enrollmentBreakdown,
    hasAnyAccess: [studentCount, staffCount, teacherCount, guardianCount].some((c) => c !== null),
  };
}
