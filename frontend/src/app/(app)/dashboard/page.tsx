import type { Metadata } from "next";

export const metadata: Metadata = { title: "Dashboard" };

export default function DashboardPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <h1 className="text-xl font-semibold">Dashboard</h1>
    </div>
  );
}
