import type { Metadata } from "next";

import { QueryProvider } from "@/providers/query-provider";

import "./globals.css";

export const metadata: Metadata = {
  title: "School Management System",
  description: "Multi-tenant school management platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" dir="ltr">
      <body>
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
