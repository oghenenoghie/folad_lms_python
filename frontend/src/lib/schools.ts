import "server-only";
import { djangoFetch } from "@/lib/session";
import type { Envelope, Paginated } from "@/lib/api-types";

export type School = {
  public_id: string;
  name: string;
  code: string;
  address: string;
  phone: string;
  email: string;
  default_grading_scheme: string;
  is_active: boolean;
};

export type Campus = {
  public_id: string;
  school: string;
  name: string;
  code: string;
  address: string;
  is_main: boolean;
  is_active: boolean;
};

export type AcademicYear = {
  public_id: string;
  school: string;
  name: string;
  start_date: string;
  end_date: string;
  is_current: boolean;
  is_active: boolean;
};

export type Term = {
  public_id: string;
  academic_year: string;
  name: string;
  sequence: number;
  start_date: string;
  end_date: string;
  is_current: boolean;
  is_active: boolean;
};

export type Department = {
  public_id: string;
  school: string;
  name: string;
  code: string;
  description: string;
  is_active: boolean;
};

/** null return means "not permitted to view" (403) — callers hide that
 * section, same 403-derived-visibility pattern as lib/dashboard.ts. */
async function listOrNull<T>(path: string): Promise<T[] | null> {
  const res = await djangoFetch(path);
  if (!res.ok) return null;
  const body: Envelope<Paginated<T>> = await res.json();
  return body.success && body.data ? body.data.results : null;
}

export async function getSchools(): Promise<School[] | null> {
  return listOrNull<School>("/api/v1/schools?page_size=100");
}

export async function getSchool(publicId: string): Promise<School | null> {
  const res = await djangoFetch(`/api/v1/schools/${publicId}`);
  if (!res.ok) return null;
  const body: Envelope<School> = await res.json();
  return body.success ? body.data : null;
}

export async function getCampuses(schoolId: string): Promise<Campus[] | null> {
  return listOrNull<Campus>(`/api/v1/campuses?school_id=${schoolId}&page_size=100`);
}

export async function getAcademicYears(schoolId: string): Promise<AcademicYear[] | null> {
  return listOrNull<AcademicYear>(`/api/v1/academic-years?school_id=${schoolId}&page_size=100`);
}

export async function getTerms(academicYearId: string): Promise<Term[] | null> {
  return listOrNull<Term>(`/api/v1/terms?academic_year_id=${academicYearId}&page_size=100`);
}

export async function getDepartments(schoolId: string): Promise<Department[] | null> {
  return listOrNull<Department>(`/api/v1/departments?school_id=${schoolId}&page_size=100`);
}
