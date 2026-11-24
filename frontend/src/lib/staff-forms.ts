import { z } from "zod";
import type { FieldConfig, SelectOption } from "@/components/schools/entity-form-dialog";

export const employmentStatusOptions: SelectOption[] = [
  { value: "active", label: "Active" },
  { value: "on_leave", label: "On Leave" },
  { value: "terminated", label: "Terminated" },
];

export function employmentStatusLabel(status: string): string {
  return employmentStatusOptions.find((option) => option.value === status)?.label ?? status;
}

// Radix `Select.Item` rejects an empty-string `value` (it reserves "" to
// mean "nothing selected" internally), so the department select's "no
// department" option needs a real sentinel string instead — translated
// back to `null` in lib/actions/staff.ts before it reaches the API.
export const NO_DEPARTMENT = "__none__";

// `school` is set once at creation and is immutable afterwards (the
// backend's perform_update drops it if sent — see actions/staff.ts), so
// create and edit use distinct schemas/field sets rather than one shared
// pair like the Schools module's forms: school only ever appears here.
export const staffCreateSchema = z.object({
  school: z.string().min(1, "School is required"),
  employee_number: z.string().min(1, "Employee number is required"),
  first_name: z.string().min(1, "First name is required"),
  last_name: z.string().min(1, "Last name is required"),
  position: z.string().min(1, "Position is required"),
  employment_status: z.enum(["active", "on_leave", "terminated"]),
  date_joined: z.string().min(1, "Date joined is required"),
});
export type StaffCreateFormValues = z.infer<typeof staffCreateSchema>;

export function staffCreateFields(schoolOptions: SelectOption[]): FieldConfig<StaffCreateFormValues>[] {
  return [
    { name: "school", label: "School", type: "select", options: schoolOptions, placeholder: "Select a school" },
    { name: "employee_number", label: "Employee number", type: "text" },
    { name: "first_name", label: "First name", type: "text" },
    { name: "last_name", label: "Last name", type: "text" },
    { name: "position", label: "Position", type: "text" },
    { name: "employment_status", label: "Employment status", type: "select", options: employmentStatusOptions },
    { name: "date_joined", label: "Date joined", type: "date" },
  ];
}

export const staffCreateDefaults: StaffCreateFormValues = {
  school: "",
  employee_number: "",
  first_name: "",
  last_name: "",
  position: "",
  employment_status: "active",
  date_joined: "",
};

// Deliberately omits `department`: at creation time there's no school
// context yet to scope its options to (the Schools module's children get
// that for free via a fixed schoolId; here department assignment is
// deferred to the edit form, once `school` — and its departments — are
// already fixed).
export const staffEditSchema = z.object({
  employee_number: z.string().min(1, "Employee number is required"),
  first_name: z.string().min(1, "First name is required"),
  last_name: z.string().min(1, "Last name is required"),
  position: z.string().min(1, "Position is required"),
  employment_status: z.enum(["active", "on_leave", "terminated"]),
  date_joined: z.string().min(1, "Date joined is required"),
  department: z.string(),
});
export type StaffEditFormValues = z.infer<typeof staffEditSchema>;

export function staffEditFields(departmentOptions: SelectOption[]): FieldConfig<StaffEditFormValues>[] {
  return [
    { name: "employee_number", label: "Employee number", type: "text" },
    { name: "first_name", label: "First name", type: "text" },
    { name: "last_name", label: "Last name", type: "text" },
    { name: "position", label: "Position", type: "text" },
    { name: "employment_status", label: "Employment status", type: "select", options: employmentStatusOptions },
    { name: "date_joined", label: "Date joined", type: "date" },
    { name: "department", label: "Department", type: "select", options: departmentOptions },
  ];
}

export const teacherSchema = z.object({
  qualification: z.string().optional(),
  specialization: z.string().optional(),
});
export type TeacherFormValues = z.infer<typeof teacherSchema>;
export const teacherFields: FieldConfig<TeacherFormValues>[] = [
  { name: "qualification", label: "Qualification", type: "text" },
  { name: "specialization", label: "Specialization", type: "text" },
];
export const teacherDefaults: TeacherFormValues = { qualification: "", specialization: "" };
