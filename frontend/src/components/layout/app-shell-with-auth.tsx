"use client";

import { useRouter } from "next/navigation";
import { type ReactNode } from "react";
import { AppShell } from "@/components/layout/app-shell";
import type { CurrentUser } from "@/lib/api-types";

export function AppShellWithAuth({ user, children }: { user: CurrentUser; children: ReactNode }) {
  const router = useRouter();

  async function handleSignOut() {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => undefined);
    router.push("/login");
    router.refresh();
  }

  const name = [user.first_name, user.last_name].filter(Boolean).join(" ");

  return (
    <AppShell user={{ name, email: user.email }} onSignOut={handleSignOut}>
      {children}
    </AppShell>
  );
}
