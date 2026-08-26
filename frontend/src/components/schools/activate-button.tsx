"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ActionResult } from "@/lib/action-result";

export function ActivateButton({
  label,
  action,
}: {
  label: string;
  action: () => Promise<ActionResult<unknown>>;
}) {
  const [pending, setPending] = useState(false);

  async function handleClick() {
    setPending(true);
    const result = await action();
    setPending(false);
    if (result.success) {
      toast.success(result.message ?? "Activated");
    } else {
      toast.error(result.message ?? "Could not activate");
    }
  }

  return (
    <Button type="button" variant="ghost" size="sm" onClick={handleClick} disabled={pending}>
      {pending && <Loader2 className="h-3 w-3 animate-spin" />}
      {label}
    </Button>
  );
}
