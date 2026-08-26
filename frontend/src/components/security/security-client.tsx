"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { QRCodeSVG } from "qrcode.react";
import { BadgeCheck, Loader2, Shield } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";

type Pending = { secret: string; otpauth_uri: string };

const schema = z.object({ code: z.string().min(1, "Enter the code from your authenticator app") });
type FormValues = z.infer<typeof schema>;

export function SecurityClient({ initialMfaEnabled }: { initialMfaEnabled: boolean }) {
  const [mfaEnabled, setMfaEnabled] = useState(initialMfaEnabled);
  const [pending, setPending] = useState<Pending | null>(null);
  const [enrolling, setEnrolling] = useState(false);

  const form = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { code: "" } });

  async function startEnrollment() {
    setEnrolling(true);
    try {
      const res = await fetch("/api/mfa/enroll", { method: "POST" });
      const body = await res.json();
      if (res.ok && body.success) {
        setPending({ secret: body.data.secret, otpauth_uri: body.data.otpauth_uri });
      } else {
        toast.error(body.message || "Could not start enrollment");
      }
    } finally {
      setEnrolling(false);
    }
  }

  async function onVerify(values: FormValues) {
    try {
      const res = await fetch("/api/mfa/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      const body = await res.json();

      if (res.ok && body.success) {
        setMfaEnabled(true);
        setPending(null);
        toast.success("Two-factor authentication is now enabled on your account.");
        return;
      }

      if (res.status === 400) {
        toast.error("Start enrollment again before verifying a code.");
        setPending(null);
        return;
      }

      form.setError("code", { message: "That code isn't valid. Check the time on your device and try again." });
    } catch {
      toast.error("Something went wrong. Please try again.");
    }
  }

  if (mfaEnabled) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Two-factor authentication</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center gap-3">
          <BadgeCheck className="h-8 w-8 text-emerald-600" />
          <div>
            <p className="text-sm font-medium">Enabled</p>
            <p className="text-sm text-muted-foreground">
              Your account requires an authenticator code at sign-in.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (pending) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Finish setting up two-factor authentication</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div>
            <p className="mb-2 text-sm">
              1. Scan this QR code with your authenticator app (Google Authenticator, 1Password, Authy,
              etc.), or enter the key manually:
            </p>
            <div className="flex items-start gap-4">
              <div className="rounded-lg border bg-white p-3">
                <QRCodeSVG value={pending.otpauth_uri} size={140} />
              </div>
              <div className="flex-1 rounded-lg bg-muted px-3 py-2 font-mono text-xs break-all">
                {pending.secret}
              </div>
            </div>
          </div>

          <Form {...form}>
            <form onSubmit={form.handleSubmit(onVerify)} className="space-y-2">
              <p className="text-sm">2. Enter the 6-digit code your app is now showing:</p>
              <div className="flex items-end gap-2">
                <FormField
                  control={form.control}
                  name="code"
                  render={({ field }) => (
                    <FormItem className="flex-1">
                      <FormLabel className="sr-only">Authenticator code</FormLabel>
                      <FormControl>
                        <Input inputMode="numeric" autoComplete="one-time-code" placeholder="123456" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <Button type="submit" disabled={form.formState.isSubmitting}>
                  {form.formState.isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                  Verify &amp; enable
                </Button>
              </div>
            </form>
          </Form>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Two-factor authentication</CardTitle>
      </CardHeader>
      <CardContent className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium">Not enabled</p>
          <p className="text-sm text-muted-foreground">
            Add an authenticator-app code to your sign-in for extra security.
          </p>
        </div>
        <Button onClick={startEnrollment} disabled={enrolling}>
          {enrolling ? <Loader2 className="h-4 w-4 animate-spin" /> : <Shield className="h-4 w-4" />}
          Enable two-factor authentication
        </Button>
      </CardContent>
    </Card>
  );
}
