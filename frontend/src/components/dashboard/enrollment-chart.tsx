"use client";

import { Doughnut } from "react-chartjs-2";
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from "chart.js";
import { useTheme } from "next-themes";

ChartJS.register(ArcElement, Tooltip, Legend);

const COLORS = ["#3b82f6", "#94a3b8", "#22c55e", "#f97316", "#ef4444"];

export function EnrollmentChart({ breakdown }: { breakdown: Record<string, number> }) {
  const { resolvedTheme } = useTheme();
  const labels = Object.keys(breakdown);
  const values = Object.values(breakdown);
  const textColor = resolvedTheme === "dark" ? "#e2e8f0" : "#334155";

  return (
    <Doughnut
      data={{
        labels,
        datasets: [
          {
            data: values,
            backgroundColor: labels.map((_, i) => COLORS[i % COLORS.length]),
            borderWidth: 0,
          },
        ],
      }}
      options={{
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { color: textColor, boxWidth: 12, padding: 16 } },
        },
      }}
    />
  );
}
