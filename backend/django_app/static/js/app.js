// App glue JS — Tailwind/HTMX/Alpine/Lucide design system (Phase 2).
// CSRF header for htmx requests is set declaratively via hx-headers on
// <body> in templates/base.html; nothing to wire up here for that.

document.addEventListener("htmx:responseError", (event) => {
  document.dispatchEvent(
    new CustomEvent("toast", {
      detail: { variant: "danger", message: "Something went wrong. Please try again." },
    })
  );
});
