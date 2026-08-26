"use client";

import { useState, type ReactNode } from "react";
import { useForm, type DefaultValues, type FieldValues, type Path, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import type { ZodType } from "zod";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { ActionResult } from "@/lib/action-result";

export type SelectOption = { value: string; label: string };

export type FieldConfig<T extends FieldValues> =
  | { name: Path<T>; label: string; type: "text" | "email" | "date" | "number" }
  | { name: Path<T>; label: string; type: "checkbox" }
  | { name: Path<T>; label: string; type: "select"; options: SelectOption[]; placeholder?: string };

export function EntityFormDialog<T extends FieldValues>({
  trigger,
  title,
  description,
  schema,
  defaultValues,
  fields,
  action,
}: {
  trigger: ReactNode;
  title: string;
  description?: string;
  schema: ZodType<T>;
  defaultValues: DefaultValues<T>;
  fields: FieldConfig<T>[];
  action: (values: T) => Promise<ActionResult<unknown>>;
}) {
  const [open, setOpen] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // zodResolver can't prove `ZodType<T>` matches react-hook-form's
  // `Resolver<T>` when T is a generic type parameter (only concrete zod
  // schemas infer cleanly) — every call site passes a concrete schema/T
  // pair, so this is a real Resolver<T> at runtime, just not provable here.
  const resolver = zodResolver(schema as ZodType<T, FieldValues>) as Resolver<T>;
  const form = useForm<T>({ resolver, defaultValues });

  async function onSubmit(values: T) {
    setFormError(null);
    const result = await action(values);
    if (result.success) {
      toast.success(result.message ?? "Saved");
      setOpen(false);
      form.reset(defaultValues);
    } else {
      setFormError(result.errors?.join(" ") || result.message || "Something went wrong");
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) {
          setFormError(null);
          form.reset(defaultValues);
        }
      }}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            {formError && (
              <Alert variant="destructive">
                <AlertDescription>{formError}</AlertDescription>
              </Alert>
            )}

            {fields.map((fieldConfig) => (
              <FormField
                key={fieldConfig.name}
                control={form.control}
                name={fieldConfig.name}
                render={({ field }) =>
                  fieldConfig.type === "checkbox" ? (
                    <FormItem className="flex flex-row items-center gap-2 space-y-0">
                      <FormControl>
                        <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                      </FormControl>
                      <FormLabel className="font-normal">{fieldConfig.label}</FormLabel>
                    </FormItem>
                  ) : fieldConfig.type === "select" ? (
                    <FormItem>
                      <FormLabel>{fieldConfig.label}</FormLabel>
                      <Select value={field.value ?? ""} onValueChange={field.onChange}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder={fieldConfig.placeholder} />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {fieldConfig.options.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  ) : (
                    <FormItem>
                      <FormLabel>{fieldConfig.label}</FormLabel>
                      <FormControl>
                        <Input
                          type={fieldConfig.type}
                          {...field}
                          value={field.value ?? ""}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )
                }
              />
            ))}

            <DialogFooter>
              <Button type="button" variant="secondary" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                Save
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
