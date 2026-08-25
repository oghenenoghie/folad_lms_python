"use client";

import type { ReactNode } from "react";
import { EntityFormDialog } from "@/components/schools/entity-form-dialog";
import { schoolSchema, schoolFields, type SchoolFormValues } from "@/lib/schools-forms";
import type { ActionResult } from "@/lib/action-result";

// Thin per-entity wrapper: a Zod schema instance can't cross the Server ->
// Client props boundary (only plain objects/built-ins can), so the schema
// and field config are imported here, client-side, rather than passed in
// as props from the Server Component pages that use this.
export function SchoolFormDialog({
  trigger,
  title,
  defaultValues,
  action,
}: {
  trigger: ReactNode;
  title: string;
  defaultValues: SchoolFormValues;
  action: (values: SchoolFormValues) => Promise<ActionResult<unknown>>;
}) {
  return (
    <EntityFormDialog
      trigger={trigger}
      title={title}
      schema={schoolSchema}
      defaultValues={defaultValues}
      fields={schoolFields}
      action={action}
    />
  );
}
