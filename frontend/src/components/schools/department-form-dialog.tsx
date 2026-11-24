"use client";

import type { ReactNode } from "react";
import { EntityFormDialog } from "@/components/schools/entity-form-dialog";
import { departmentSchema, departmentFields, type DepartmentFormValues } from "@/lib/schools-forms";
import type { ActionResult } from "@/lib/action-result";

export function DepartmentFormDialog({
  trigger,
  title,
  defaultValues,
  action,
}: {
  trigger: ReactNode;
  title: string;
  defaultValues: DepartmentFormValues;
  action: (values: DepartmentFormValues) => Promise<ActionResult<unknown>>;
}) {
  return (
    <EntityFormDialog
      trigger={trigger}
      title={title}
      schema={departmentSchema}
      defaultValues={defaultValues}
      fields={departmentFields}
      action={action}
    />
  );
}
