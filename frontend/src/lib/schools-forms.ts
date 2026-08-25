import { z } from "zod";
import type { FieldConfig } from "@/components/schools/entity-form-dialog";

export const schoolSchema = z.object({
  name: z.string().min(1, "Name is required"),
  code: z.string().min(1, "Code is required"),
  address: z.string().optional(),
  phone: z.string().optional(),
  email: z.string().email("Enter a valid email").or(z.literal("")).optional(),
  default_grading_scheme: z.string().optional(),
  is_active: z.boolean(),
});
export type SchoolFormValues = z.infer<typeof schoolSchema>;
export const schoolFields: FieldConfig<SchoolFormValues>[] = [
  { name: "name", label: "Name", type: "text" },
  { name: "code", label: "Code", type: "text" },
  { name: "address", label: "Address", type: "text" },
  { name: "phone", label: "Phone", type: "text" },
  { name: "email", label: "Email", type: "email" },
  { name: "default_grading_scheme", label: "Default grading scheme", type: "text" },
  { name: "is_active", label: "Active", type: "checkbox" },
];
export const schoolDefaults: SchoolFormValues = {
  name: "",
  code: "",
  address: "",
  phone: "",
  email: "",
  default_grading_scheme: "",
  is_active: true,
};

export const campusSchema = z.object({
  name: z.string().min(1, "Name is required"),
  code: z.string().min(1, "Code is required"),
  address: z.string().optional(),
  is_main: z.boolean(),
  is_active: z.boolean(),
});
export type CampusFormValues = z.infer<typeof campusSchema>;
export const campusFields: FieldConfig<CampusFormValues>[] = [
  { name: "name", label: "Name", type: "text" },
  { name: "code", label: "Code", type: "text" },
  { name: "address", label: "Address", type: "text" },
  { name: "is_main", label: "Main campus", type: "checkbox" },
  { name: "is_active", label: "Active", type: "checkbox" },
];
export const campusDefaults: CampusFormValues = { name: "", code: "", address: "", is_main: false, is_active: true };

export const academicYearSchema = z.object({
  name: z.string().min(1, "Name is required"),
  start_date: z.string().min(1, "Start date is required"),
  end_date: z.string().min(1, "End date is required"),
  is_active: z.boolean(),
});
export type AcademicYearFormValues = z.infer<typeof academicYearSchema>;
export const academicYearFields: FieldConfig<AcademicYearFormValues>[] = [
  { name: "name", label: "Name", type: "text" },
  { name: "start_date", label: "Start date", type: "date" },
  { name: "end_date", label: "End date", type: "date" },
  { name: "is_active", label: "Active", type: "checkbox" },
];
export const academicYearDefaults: AcademicYearFormValues = {
  name: "",
  start_date: "",
  end_date: "",
  is_active: true,
};

export const termSchema = z.object({
  name: z.string().min(1, "Name is required"),
  sequence: z.coerce.number().int().min(1, "Sequence must be at least 1"),
  start_date: z.string().min(1, "Start date is required"),
  end_date: z.string().min(1, "End date is required"),
  is_active: z.boolean(),
});
export type TermFormValues = z.infer<typeof termSchema>;
export const termFields: FieldConfig<TermFormValues>[] = [
  { name: "name", label: "Name", type: "text" },
  { name: "sequence", label: "Sequence", type: "number" },
  { name: "start_date", label: "Start date", type: "date" },
  { name: "end_date", label: "End date", type: "date" },
  { name: "is_active", label: "Active", type: "checkbox" },
];
export const termDefaults: TermFormValues = { name: "", sequence: 1, start_date: "", end_date: "", is_active: true };

export const departmentSchema = z.object({
  name: z.string().min(1, "Name is required"),
  code: z.string().min(1, "Code is required"),
  description: z.string().optional(),
  is_active: z.boolean(),
});
export type DepartmentFormValues = z.infer<typeof departmentSchema>;
export const departmentFields: FieldConfig<DepartmentFormValues>[] = [
  { name: "name", label: "Name", type: "text" },
  { name: "code", label: "Code", type: "text" },
  { name: "description", label: "Description", type: "text" },
  { name: "is_active", label: "Active", type: "checkbox" },
];
export const departmentDefaults: DepartmentFormValues = { name: "", code: "", description: "", is_active: true };
