"""Shared CRUD scaffolding for the module pages (Phase 6 onward). Every
module's list/create/update/delete views follow the same shape — thin
views, fat services, permission-gated per apps.accounts.permissions —
so it's factored here once instead of repeated per model.

The create/update flow assumes the *form* is already rendered inline
(inside a hidden `{% ui_modal %}`) as part of the parent list/detail
page's own GET — these views only ever handle the POST: on success they
return an `HX-Redirect` for htmx to follow (a full navigation, so the
modal simply isn't part of the next page); on validation error they
re-render just the `<form>` partial for htmx to swap back into the
still-open modal (see templates/web/_generic_form.html).
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic.edit import FormMixin

FORM_PARTIAL = "web/_generic_form.html"


def _redirect_response(request, url: str):
    """htmx requests get a 204 + HX-Redirect (a full navigation, so the
    modal that triggered this simply isn't part of the next page). A
    plain form POST — htmx JS didn't load, or a client without JS — gets
    a real HTTP redirect instead, so the action still completes and the
    user still lands on the right page; only the SPA-like partial swap
    on validation errors is htmx-only.
    """
    if request.headers.get("HX-Request") == "true":
        response = HttpResponse(status=204)
        response["HX-Redirect"] = url
        return response
    return redirect(url)


class WebPermissionMixin(LoginRequiredMixin):
    login_url = reverse_lazy("web:login")
    permission_code = ""

    def dispatch(self, request, *args, **kwargs):
        if (
            request.user.is_authenticated
            and self.permission_code
            and not self.request_user_can(request)
        ):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def request_user_can(self, request) -> bool:
        from apps.web.permissions import can

        return can(request.user, self.permission_code)


class ServiceFormView(WebPermissionMixin, FormMixin, View):
    """POST-only: renders `FORM_PARTIAL` on validation error, otherwise
    calls `save(form)` (implemented by the subclass, calling the real
    service function) and redirects via HX-Redirect."""

    template_name = FORM_PARTIAL
    form_post_url_name = ""  # used to build the form's own hx-post target on re-render

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if not form.is_valid():
            return self.form_invalid(form)
        return self.form_valid(form)

    def form_invalid(self, form):
        return render(self.request, self.template_name, self.get_form_context(form))

    def form_valid(self, form):
        from django.db import IntegrityError

        try:
            self.save(form)
        except IntegrityError:
            # ModelForm's own validate_unique() only covers fields present
            # on the form — the parent FK (school / academic_year) isn't
            # one of them (see forms/schools.py), so a uniqueness conflict
            # scoped to that parent surfaces here instead, same root cause
            # as apps.core.generics.EnvelopeCreateMixin's 409 on the API.
            form.add_error(None, "A record with these values already exists.")
            return self.form_invalid(form)
        return _redirect_response(self.request, str(self.get_success_url()))

    def save(self, form):
        raise NotImplementedError

    def get_form_context(self, form):
        return {"form": form, "post_url": self.request.path}


class ServiceActionView(WebPermissionMixin, View):
    """POST-only for a one-off service action with no form of its own
    (e.g. "activate this academic year") — same HX-Redirect contract as
    ServiceFormView/ServiceDeleteView."""

    def post(self, request, *args, **kwargs):
        self.perform_action()
        return _redirect_response(request, str(self.get_success_url()))

    def perform_action(self):
        raise NotImplementedError

    def get_success_url(self):
        raise NotImplementedError


class ServiceDeleteView(WebPermissionMixin, View):
    """POST-only delete — the confirm prompt is htmx's own `hx-confirm`
    on the trigger button (see components/button.html), not a modal."""

    def post(self, request, *args, **kwargs):
        self.delete_instance()
        return _redirect_response(request, str(self.get_success_url()))

    def delete_instance(self):
        raise NotImplementedError

    def get_success_url(self):
        raise NotImplementedError
