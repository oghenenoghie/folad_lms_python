"use client";

import type { ReactNode } from "react";
import { EntityFormDialog } from "@/components/schools/entity-form-dialog";
import { teacherSchema, teacherFields, type TeacherFormValues } from "@/lib/staff-forms";
import type { ActionResult } from "@/lib/action-result";

export function TeacherFormDialog({
  trigger,
  title,
  defaultValues,
  action,
}: {
  trigger: ReactNode;
  title: string;
  defaultValues: TeacherFormValues;
  action: (values: TeacherFormValues) => Promise<ActionResult<unknown>>;
}) {
  return (
    <EntityFormDialog
      trigger={trigger}
      title={title}
      schema={teacherSchema}
      defaultValues={defaultValues}
      fields={teacherFields}
      action={action}
    />
  );
}
