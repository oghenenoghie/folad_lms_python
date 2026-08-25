"use server";

import { revalidatePath } from "next/cache";
import { authorizedDjangoFetch } from "@/lib/session";
import { toActionResult, type ActionResult } from "@/lib/action-result";
import { NO_DEPARTMENT } from "@/lib/staff-forms";

async function call<T>(path: string, method: string, body?: unknown): Promise<ActionResult<T>> {
  const res = await authorizedDjangoFetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return toActionResult<T>(res);
}

// --- Staff ---
export async function createStaff(input: Record<string, unknown>) {
  const result = await call("/api/v1/staff", "POST", input);
  if (result.success) revalidatePath("/staff");
  return result;
}

export async function updateStaff(publicId: string, input: Record<string, unknown>) {
  // `school` is immutable after creation (apps/staff/views.py's
  // perform_update drops it server-side regardless), so the edit form
  // never submits it — nothing to strip here. `department` does need
  // translating: the select's "no department" option submits the
  // NO_DEPARTMENT sentinel (Radix Select disallows an empty-string
  // item value), which the backend's SlugRelatedField would otherwise
  // try, and fail, to resolve as a real department.
  const payload = { ...input, department: input.department === NO_DEPARTMENT ? null : input.department };
  const result = await call(`/api/v1/staff/${publicId}`, "PATCH", payload);
  if (result.success) {
    revalidatePath("/staff");
    revalidatePath(`/staff/${publicId}`);
  }
  return result;
}

export async function deleteStaff(publicId: string) {
  const result = await call(`/api/v1/staff/${publicId}`, "DELETE");
  if (result.success) revalidatePath("/staff");
  return result;
}

// --- Teachers ---
export async function createTeacher(staffId: string, input: Record<string, unknown>) {
  const result = await call("/api/v1/teachers", "POST", { ...input, staff: staffId });
  if (result.success) revalidatePath(`/staff/${staffId}`);
  return result;
}

export async function updateTeacher(staffId: string, publicId: string, input: Record<string, unknown>) {
  const result = await call(`/api/v1/teachers/${publicId}`, "PATCH", input);
  if (result.success) revalidatePath(`/staff/${staffId}`);
  return result;
}

export async function deleteTeacher(staffId: string, publicId: string) {
  const result = await call(`/api/v1/teachers/${publicId}`, "DELETE");
  if (result.success) revalidatePath(`/staff/${staffId}`);
  return result;
}
