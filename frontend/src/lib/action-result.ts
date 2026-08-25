import type { Envelope } from "@/lib/api-types";

export type ActionResult<T = unknown> = {
  success: boolean;
  message: string | null;
  errors: string[] | null;
  data: T | null;
};

export async function toActionResult<T>(res: Response): Promise<ActionResult<T>> {
  const body: Envelope<T> = await res.json().catch(() => ({
    success: false,
    data: null,
    message: "Unexpected response from server",
    errors: null,
  }));
  return { success: res.ok && body.success, message: body.message, errors: body.errors, data: body.data };
}
