"""Overrides Django's built-in "en" locale DATE_INPUT_FORMATS (see
FORMAT_MODULE_PATH in settings/base.py). A plain `settings.DATE_INPUT_FORMATS`
is silently ignored whenever localization finds a format for the active
language — which it always does here, since Django ships one for "en" —
so this is the actual place Django looks first (get_format_modules() puts
FORMAT_MODULE_PATH ahead of django.conf.locale.en). en-us's own default is
US-centric (month-first) and neither it nor any locale's default includes
a dash-separated day-abbreviated-month style (e.g. "02-Aug-2017") — a
format staff naturally type by hand even though it isn't what the admin's
own calendar-picker widget produces (that inserts plain ISO). Extend,
don't replace, so the ISO/US formats still work too.
"""
DATE_INPUT_FORMATS = [
    "%Y-%m-%d",  # 2017-08-02 (ISO; what the calendar-picker widget inserts)
    "%m/%d/%Y",  # 08/02/2017
    "%d/%m/%Y",  # 02/08/2017
    "%d-%m-%Y",  # 02-08-2017
    "%d-%b-%Y",  # 02-Aug-2017
    "%d %b %Y",  # 02 Aug 2017
    "%d-%B-%Y",  # 02-August-2017
    "%d %B %Y",  # 02 August 2017
]
