"use client";

import type { ReactNode } from "react";
import { EntityFormDialog } from "@/components/schools/entity-form-dialog";
import { termSchema, termFields, type TermFormValues } from "@/lib/schools-forms";
import type { ActionResult } from "@/lib/action-result";

export function TermFormDialog({
  trigger,
  title,
  defaultValues,
  action,
}: {
  trigger: ReactNode;
  title: string;
  defaultValues: TermFormValues;
  action: (values: TermFormValues) => Promise<ActionResult<unknown>>;
}) {
  return (
    <EntityFormDialog
      trigger={trigger}
      title={title}
      schema={termSchema}
      defaultValues={defaultValues}
      fields={termFields}
      action={action}
    />
  );
}
