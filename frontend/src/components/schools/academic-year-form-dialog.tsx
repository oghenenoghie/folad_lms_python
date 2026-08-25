"use client";

import type { ReactNode } from "react";
import { EntityFormDialog } from "@/components/schools/entity-form-dialog";
import { academicYearSchema, academicYearFields, type AcademicYearFormValues } from "@/lib/schools-forms";
import type { ActionResult } from "@/lib/action-result";

export function AcademicYearFormDialog({
  trigger,
  title,
  defaultValues,
  action,
}: {
  trigger: ReactNode;
  title: string;
  defaultValues: AcademicYearFormValues;
  action: (values: AcademicYearFormValues) => Promise<ActionResult<unknown>>;
}) {
  return (
    <EntityFormDialog
      trigger={trigger}
      title={title}
      schema={academicYearSchema}
      defaultValues={defaultValues}
      fields={academicYearFields}
      action={action}
    />
  );
}
