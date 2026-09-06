"""Design-system component tags (Phase 2, UI_MIGRATION_PLAN.md).

Two shapes, matching what each component actually needs:

- `inclusion_tag` for self-contained, data-driven atoms (icon, button,
  badge, alert, avatar, empty state, loading spinner, breadcrumbs,
  pagination) — everything they render comes from their arguments.
- A small block-tag helper (`_block_component`) for the handful of
  components that wrap arbitrary caller-supplied markup (card, modal,
  dropdown) — Django's inclusion tags can't capture a template body, so
  these parse `{% ui_card %}...{% end_ui_card %}` directly and render the
  enclosed nodelist into a `content` variable.

No JS icon library is loaded at runtime: `ui_icon` inlines the vendored
Lucide SVG source directly (static/vendor/lucide/*.svg), read once and
cached in-process — consistent with WhiteNoise already serving every
other static asset from disk, and avoids shipping a JS bundle just for
icons.
"""

import re
from functools import lru_cache

from django import template
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

register = template.Library()

# The vendored source (`<svg\n  class="lucide ...">`) puts a newline, not a
# space, right after the tag name, so a literal "<svg " substring never
# matched it — every ui_icon() call silently ignored css_class. Matches
# "<svg" followed by any whitespace, without consuming it, so this works
# regardless of the vendored file's exact formatting.
_SVG_OPEN_TAG = re.compile(r"<svg(?=\s)")

_LUCIDE_DIR = settings.DJANGO_APP_DIR / "static" / "vendor" / "lucide"


@lru_cache(maxsize=128)
def _load_icon_svg(name: str) -> str:
    path = _LUCIDE_DIR / f"{name}.svg"
    if not path.exists():
        return ""
    return path.read_text()


@register.simple_tag
def ui_icon(name: str, css_class: str = "h-5 w-5") -> str:
    svg = _load_icon_svg(name)
    if not svg:
        return ""
    svg = _SVG_OPEN_TAG.sub(f'<svg class="{css_class}"', svg, count=1)
    return mark_safe(svg)


@register.inclusion_tag("components/button.html")
def ui_button(
    label: str,
    variant: str = "primary",
    icon: str = "",
    type: str = "button",
    href: str = "",
    hx_get: str = "",
    hx_post: str = "",
    hx_target: str = "",
    hx_confirm: str = "",
    disabled: bool = False,
):
    return {
        "label": label,
        "variant": variant,
        "icon": icon,
        "type": type,
        "href": href,
        "hx_get": hx_get,
        "hx_post": hx_post,
        "hx_target": hx_target,
        "hx_confirm": hx_confirm,
        "disabled": disabled,
    }


@register.inclusion_tag("components/badge.html")
def ui_badge(label: str, color: str = "gray"):
    return {"label": label, "color": color}


@register.inclusion_tag("components/alert.html")
def ui_alert(message: str, variant: str = "info", title: str = ""):
    icons = {"info": "info", "success": "circle-check", "warning": "alert-triangle", "danger": "alert-circle"}
    return {"message": message, "variant": variant, "title": title, "icon": icons.get(variant, "info")}


@register.inclusion_tag("components/avatar.html")
def ui_avatar(name: str, size: str = "h-8 w-8"):
    initials = "".join(part[0].upper() for part in name.split()[:2]) or "?"
    return {"initials": initials, "size": size}


@register.inclusion_tag("components/empty_state.html")
def ui_empty_state(title: str, description: str = "", icon: str = "inbox"):
    return {"title": title, "description": description, "icon": icon}


@register.inclusion_tag("components/loading.html")
def ui_loading(label: str = "Loading…"):
    return {"label": label}


@register.inclusion_tag("components/breadcrumbs.html")
def ui_breadcrumbs(items):
    """`items`: list of (label, url_or_none) tuples; last item is the
    current page and should pass url=None."""
    return {"items": items}


@register.inclusion_tag("components/pagination.html", takes_context=True)
def ui_pagination(context, page, hx_target: str = ""):
    """`page` is a `django.core.paginator.Page` from a template list view's
    own `Paginator` (server-rendered pages query the ORM directly — see
    §5 UI_MIGRATION_PLAN.md — this is deliberately separate from the JSON
    API's DRF `EnvelopePageNumberPagination`, which paginates a different
    response shape for a different client)."""
    request = context.get("request")
    querystring = request.GET.copy() if request else {}
    querystring.pop("page", None)
    base_qs = querystring.urlencode()
    return {"page": page, "base_qs": base_qs, "hx_target": hx_target}


# --- Block components (card / modal / dropdown) -----------------------

class _ComponentNode(template.Node):
    def __init__(self, nodelist, template_name, kwargs):
        self.nodelist = nodelist
        self.template_name = template_name
        self.kwargs = kwargs

    def render(self, context):
        content = self.nodelist.render(context)
        resolved = {key: value.resolve(context) for key, value in self.kwargs.items()}
        resolved["content"] = mark_safe(content)
        return render_to_string(self.template_name, resolved, request=context.get("request"))


def _block_component(register_, tag_name, end_tag_name, template_name):
    def compile_fn(parser, token):
        bits = token.split_contents()[1:]
        kwargs = {}
        for bit in bits:
            key, _, value = bit.partition("=")
            kwargs[key] = parser.compile_filter(value)
        nodelist = parser.parse((end_tag_name,))
        parser.delete_first_token()
        return _ComponentNode(nodelist, template_name, kwargs)

    register_.tag(tag_name, compile_fn)


_block_component(register, "ui_card", "end_ui_card", "components/card.html")
_block_component(register, "ui_modal", "end_ui_modal", "components/modal.html")
_block_component(register, "ui_dropdown", "end_ui_dropdown", "components/dropdown.html")
