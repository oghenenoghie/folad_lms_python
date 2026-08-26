"use client";

import type { ReactNode } from "react";
import { EntityFormDialog, type SelectOption } from "@/components/schools/entity-form-dialog";
import {
  staffCreateSchema,
  staffCreateFields,
  type StaffCreateFormValues,
  staffEditSchema,
  staffEditFields,
  type StaffEditFormValues,
} from "@/lib/staff-forms";
import type { ActionResult } from "@/lib/action-result";

export function StaffCreateFormDialog({
  trigger,
  title,
  defaultValues,
  schoolOptions,
  action,
}: {
  trigger: ReactNode;
  title: string;
  defaultValues: StaffCreateFormValues;
  schoolOptions: SelectOption[];
  action: (values: StaffCreateFormValues) => Promise<ActionResult<unknown>>;
}) {
  return (
    <EntityFormDialog
      trigger={trigger}
      title={title}
      schema={staffCreateSchema}
      defaultValues={defaultValues}
      fields={staffCreateFields(schoolOptions)}
      action={action}
    />
  );
}

export function StaffEditFormDialog({
  trigger,
  title,
  defaultValues,
  departmentOptions,
  action,
}: {
  trigger: ReactNode;
  title: string;
  defaultValues: StaffEditFormValues;
  departmentOptions: SelectOption[];
  action: (values: StaffEditFormValues) => Promise<ActionResult<unknown>>;
}) {
  return (
    <EntityFormDialog
      trigger={trigger}
      title={title}
      schema={staffEditSchema}
      defaultValues={defaultValues}
      fields={staffEditFields(departmentOptions)}
      action={action}
    />
  );
}
