"use server";

import { revalidatePath } from "next/cache";
import { authorizedDjangoFetch } from "@/lib/session";
import { toActionResult, type ActionResult } from "@/lib/action-result";

async function call<T>(path: string, method: string, body?: unknown): Promise<ActionResult<T>> {
  const res = await authorizedDjangoFetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return toActionResult<T>(res);
}

// --- Schools ---
export async function createSchool(input: Record<string, unknown>) {
  const result = await call("/api/v1/schools", "POST", input);
  if (result.success) revalidatePath("/schools");
  return result;
}

export async function updateSchool(publicId: string, input: Record<string, unknown>) {
  const result = await call(`/api/v1/schools/${publicId}`, "PATCH", input);
  if (result.success) {
    revalidatePath("/schools");
    revalidatePath(`/schools/${publicId}`);
  }
  return result;
}

export async function deleteSchool(publicId: string) {
  const result = await call(`/api/v1/schools/${publicId}`, "DELETE");
  if (result.success) revalidatePath("/schools");
  return result;
}

// --- Campuses ---
export async function createCampus(schoolId: string, input: Record<string, unknown>) {
  const result = await call("/api/v1/campuses", "POST", { ...input, school: schoolId });
  if (result.success) revalidatePath(`/schools/${schoolId}`);
  return result;
}

export async function updateCampus(schoolId: string, publicId: string, input: Record<string, unknown>) {
  const result = await call(`/api/v1/campuses/${publicId}`, "PATCH", input);
  if (result.success) revalidatePath(`/schools/${schoolId}`);
  return result;
}

export async function deleteCampus(schoolId: string, publicId: string) {
  const result = await call(`/api/v1/campuses/${publicId}`, "DELETE");
  if (result.success) revalidatePath(`/schools/${schoolId}`);
  return result;
}

// --- Academic years ---
export async function createAcademicYear(schoolId: string, input: Record<string, unknown>) {
  const result = await call("/api/v1/academic-years", "POST", { ...input, school: schoolId });
  if (result.success) revalidatePath(`/schools/${schoolId}`);
  return result;
}

export async function updateAcademicYear(schoolId: string, publicId: string, input: Record<string, unknown>) {
  const result = await call(`/api/v1/academic-years/${publicId}`, "PATCH", input);
  if (result.success) revalidatePath(`/schools/${schoolId}`);
  return result;
}

export async function deleteAcademicYear(schoolId: string, publicId: string) {
  const result = await call(`/api/v1/academic-years/${publicId}`, "DELETE");
  if (result.success) revalidatePath(`/schools/${schoolId}`);
  return result;
}

export async function activateAcademicYear(schoolId: string, publicId: string) {
  const result = await call(`/api/v1/academic-years/${publicId}/activate`, "POST");
  if (result.success) revalidatePath(`/schools/${schoolId}`);
  return result;
}

// --- Terms ---
export async function createTerm(schoolId: string, academicYearId: string, input: Record<string, unknown>) {
  const result = await call("/api/v1/terms", "POST", { ...input, academic_year: academicYearId });
  if (result.success) revalidatePath(`/schools/${schoolId}`);
  return result;
}

export async function updateTerm(schoolId: string, publicId: string, input: Record<string, unknown>) {
  const result = await call(`/api/v1/terms/${publicId}`, "PATCH", input);
  if (result.success) revalidatePath(`/schools/${schoolId}`);
  return result;
}

export async function deleteTerm(schoolId: string, publicId: string) {
  const result = await call(`/api/v1/terms/${publicId}`, "DELETE");
  if (result.success) revalidatePath(`/schools/${schoolId}`);
  return result;
}

export async function activateTerm(schoolId: string, publicId: string) {
  const result = await call(`/api/v1/terms/${publicId}/activate`, "POST");
  if (result.success) revalidatePath(`/schools/${schoolId}`);
  return result;
}

// --- Departments ---
export async function createDepartment(schoolId: string, input: Record<string, unknown>) {
  const result = await call("/api/v1/departments", "POST", { ...input, school: schoolId });
  if (result.success) revalidatePath(`/schools/${schoolId}`);
  return result;
}

export async function updateDepartment(schoolId: string, publicId: string, input: Record<string, unknown>) {
  const result = await call(`/api/v1/departments/${publicId}`, "PATCH", input);
  if (result.success) revalidatePath(`/schools/${schoolId}`);
  return result;
}

export async function deleteDepartment(schoolId: string, publicId: string) {
  const result = await call(`/api/v1/departments/${publicId}`, "DELETE");
  if (result.success) revalidatePath(`/schools/${schoolId}`);
  return result;
}
