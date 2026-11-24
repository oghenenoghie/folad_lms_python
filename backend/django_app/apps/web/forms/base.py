"""Applies the design system's field classes to every Form/ModelForm
field automatically, so a form declaration only needs `Meta.model` +
`Meta.fields` — no per-field widget boilerplate (Phase 6 onward)."""
from django import forms

_TEXT_LIKE_CLASS = "field-input"
_CHECKBOX_CLASS = "h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-600"


class StyledFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = _CHECKBOX_CLASS if isinstance(field.widget, forms.CheckboxInput) else _TEXT_LIKE_CLASS
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} {css_class}".strip()


class StyledForm(StyledFormMixin, forms.Form):
    pass


class StyledModelForm(StyledFormMixin, forms.ModelForm):
    pass
