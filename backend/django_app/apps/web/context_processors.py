"""Sidebar nav structure for the app shell (templates/layouts/app.html).
One list, shared by every apps.web page, kept here rather than duplicated
per-template. Only entries with a real, built page get `enabled=True` and
a `url` — see UI_MIGRATION_PLAN.md §3: the other school-management modules
named in later phases don't have server-rendered pages yet, so they're
listed (previewing the intended IA) but deliberately not clickable rather
than linking to something that doesn't exist yet.
"""
from django.urls import reverse


def nav_items(request):
    if not request.path.startswith("/app/"):
        return {}

    return {
        "nav_sections": [
            {
                "items": [
                    {"label": "Dashboard", "icon": "layout-dashboard", "url": reverse("web:home"), "enabled": True},
                ]
            },
            {
                "heading": "School",
                "items": [
                    {"label": "Students", "icon": "graduation-cap", "enabled": False},
                    {"label": "Staff & teachers", "icon": "briefcase", "enabled": False},
                    {"label": "Parents & guardians", "icon": "heart-handshake", "enabled": False},
                    {"label": "Schools & academics", "icon": "building-2", "enabled": False},
                ]
            },
            {
                "heading": "Administration",
                "items": [
                    {"label": "Users & roles", "icon": "shield", "enabled": False},
                ]
            },
        ]
    }
