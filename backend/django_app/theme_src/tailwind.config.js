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
        // Matches the Next.js frontend's design tokens (src/app/globals.css
        // there) — a warm cream/forest-green theme, not this app's own
        // invention. brand-600 is that palette's --primary (#104625)
        // exactly; the rest of the scale is interpolated around it so
        // existing brand-50..950 utility classes (hover/focus states,
        // badges, icons) stay meaningful without touching every template.
        brand: {
          50: "#eef7f1",
          100: "#d7ecdd",
          200: "#b0d9bc",
          300: "#7ebd93",
          400: "#4f9d6d",
          500: "#2c7a4d",
          600: "#104625",
          700: "#0d3a1f",
          800: "#0a2e19",
          900: "#082414",
          950: "#04140b",
        },
        // --background/--foreground pulled directly from the frontend's
        // CSS variables (see input.css's :root/.dark below) so the page
        // canvas and default text match exactly in both themes.
        background: "var(--app-background)",
        foreground: "var(--app-foreground)",
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
