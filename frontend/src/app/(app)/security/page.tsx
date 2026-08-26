import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/session";
import { SecurityClient } from "@/components/security/security-client";

export const metadata: Metadata = { title: "Security" };

export default async function SecurityPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login");

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <div>
        <h1 className="text-xl font-semibold">Security</h1>
        <p className="text-sm text-muted-foreground">Two-factor authentication for your account</p>
      </div>
      <SecurityClient initialMfaEnabled={user.mfa_enabled} />
    </div>
  );
}
