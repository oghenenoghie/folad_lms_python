"use client";

import type { ReactNode } from "react";
import { EntityFormDialog } from "@/components/schools/entity-form-dialog";
import { campusSchema, campusFields, type CampusFormValues } from "@/lib/schools-forms";
import type { ActionResult } from "@/lib/action-result";

export function CampusFormDialog({
  trigger,
  title,
  defaultValues,
  action,
}: {
  trigger: ReactNode;
  title: string;
  defaultValues: CampusFormValues;
  action: (values: CampusFormValues) => Promise<ActionResult<unknown>>;
}) {
  return (
    <EntityFormDialog
      trigger={trigger}
      title={title}
      schema={campusSchema}
      defaultValues={defaultValues}
      fields={campusFields}
      action={action}
    />
  );
}
