import type { ReactNode } from "react";
import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/session";
import { AppShellWithAuth } from "@/components/layout/app-shell-with-auth";

export default async function AppLayout({ children }: { children: ReactNode }) {
  const user = await getCurrentUser();
  if (!user) {
    redirect("/login");
  }

  return <AppShellWithAuth user={user}>{children}</AppShellWithAuth>;
}
