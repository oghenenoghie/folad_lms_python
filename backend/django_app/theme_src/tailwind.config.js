/**
 * Tailwind source config for the school-management SaaS UI. Compiled by
 * the standalone Tailwind CLI (no Node/npm — see infrastructure/docker/
 * backend.Dockerfile) into django_app/static/css/app.css, which
 * WhiteNoise/collectstatic then serves like any other static asset.
 */
module.exports = {
  darkMode: "class",
  // Resolved relative to the Tailwind CLI's cwd (django_app/ — see the
  // Dockerfile build step and the local `tailwindcss -c theme_src/...`
  // invocation), not relative to this config file.
  content: [
    "templates/**/*.html",
    "apps/**/templates/**/*.html",
    "apps/**/templatetags/*.py",
  ],
  // Tailwind's content scanner only sees the literal `class="badge-{{ color }}"`
  // text in templates, never the interpolated result, so any `@layer
  // components` class built from a Django variable (badge/alert color,
  // active nav/pagination state) would otherwise get purged as "unused".
  // Every component class with a variable name maps to one of these.
  safelist: [
    "badge-gray", "badge-green", "badge-red", "badge-yellow", "badge-blue",
    "alert-info", "alert-success", "alert-warning", "alert-danger",
    "btn-primary", "btn-secondary", "btn-danger", "btn-ghost",
    "nav-item", "nav-item-active",
    "pagination-link", "pagination-link-active",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eff6ff",
          100: "#dbeafe",
          200: "#bfdbfe",
          300: "#93c5fd",
          400: "#60a5fa",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
          800: "#1e40af",
          900: "#1e3a8a",
          950: "#172554",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
