"""Public, unauthenticated pages — the site's front door, as opposed to
everything else under `apps.web`, which is session-gated behind
`WebPermissionMixin`/`LoginRequiredMixin` (see views/base.py, views/dashboard.py)."""

from django.urls import reverse_lazy
from django.views.generic import TemplateView


class LandingView(TemplateView):
    template_name = "web/landing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # web:home is LoginRequiredMixin-gated (see views/dashboard.py) —
        # an unauthenticated visitor following this link lands on
        # /app/login instead, same as hitting /app/ directly.
        context["dashboard_url"] = reverse_lazy("web:home")
        return context
