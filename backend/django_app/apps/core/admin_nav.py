"""Explicit UNFOLD["SIDEBAR"]["navigation"] config (see config/settings/base.py).
Unfold only renders icons through this hand-built list — its fallback
(when this is empty) is Django's own unstyled admin/app_list.html, which
has no icon support at all. Each item's `permission` mirrors what the
model's changelist view already enforces (`view_<model>`), so a staff user
without access to a given model still won't see it linked here either.
"""
from django.urls import reverse_lazy


def _view_perm(app_label: str, model_name: str):
    codename = f"{app_label}.view_{model_name}"
    return lambda request: request.user.has_perm(codename)


NAVIGATION = [
    {
        "items": [
            {
                "title": "Dashboard",
                "icon": "dashboard",
                "link": reverse_lazy("admin:index"),
            },
        ],
    },
    {
        "title": "Accounts",
        "separator": True,
        "items": [
            {
                "title": "Users",
                "icon": "person",
                "link": reverse_lazy("admin:accounts_user_changelist"),
                "permission": _view_perm("accounts", "user"),
            },
            {
                "title": "Roles",
                "icon": "verified_user",
                "link": reverse_lazy("admin:accounts_role_changelist"),
                "permission": _view_perm("accounts", "role"),
            },
            {
                "title": "Permissions",
                "icon": "key",
                "link": reverse_lazy("admin:accounts_permission_changelist"),
                "permission": _view_perm("accounts", "permission"),
            },
            {
                "title": "Role permissions",
                "icon": "rule",
                "link": reverse_lazy("admin:accounts_rolepermission_changelist"),
                "permission": _view_perm("accounts", "rolepermission"),
            },
            {
                "title": "User roles",
                "icon": "assignment_ind",
                "link": reverse_lazy("admin:accounts_userrole_changelist"),
                "permission": _view_perm("accounts", "userrole"),
            },
            {
                "title": "Login history",
                "icon": "history",
                "link": reverse_lazy("admin:accounts_loginhistory_changelist"),
                "permission": _view_perm("accounts", "loginhistory"),
            },
            {
                "title": "Failed login attempts",
                "icon": "gpp_maybe",
                "link": reverse_lazy("admin:accounts_failedloginattempt_changelist"),
                "permission": _view_perm("accounts", "failedloginattempt"),
            },
        ],
    },
    {
        "title": "Authentication and Authorization",
        "items": [
            {
                "title": "Groups",
                "icon": "diversity_3",
                "link": reverse_lazy("admin:auth_group_changelist"),
                "permission": _view_perm("auth", "group"),
            },
        ],
    },
    {
        "title": "Tenancy",
        "items": [
            {
                "title": "Organizations",
                "icon": "corporate_fare",
                "link": reverse_lazy("admin:tenancy_organization_changelist"),
                "permission": _view_perm("tenancy", "organization"),
            },
        ],
    },
    {
        "title": "Schools",
        "items": [
            {
                "title": "Schools",
                "icon": "school",
                "link": reverse_lazy("admin:schools_school_changelist"),
                "permission": _view_perm("schools", "school"),
            },
            {
                "title": "Campuses",
                "icon": "location_city",
                "link": reverse_lazy("admin:schools_campus_changelist"),
                "permission": _view_perm("schools", "campus"),
            },
            {
                "title": "Academic years",
                "icon": "calendar_month",
                "link": reverse_lazy("admin:schools_academicyear_changelist"),
                "permission": _view_perm("schools", "academicyear"),
            },
            {
                "title": "Terms",
                "icon": "date_range",
                "link": reverse_lazy("admin:schools_term_changelist"),
                "permission": _view_perm("schools", "term"),
            },
            {
                "title": "Departments",
                "icon": "apartment",
                "link": reverse_lazy("admin:schools_department_changelist"),
                "permission": _view_perm("schools", "department"),
            },
        ],
    },
    {
        "title": "Students",
        "items": [
            {
                "title": "Students",
                "icon": "groups",
                "link": reverse_lazy("admin:students_student_changelist"),
                "permission": _view_perm("students", "student"),
            },
        ],
    },
    {
        "title": "Staff",
        "items": [
            {
                "title": "Staff",
                "icon": "badge",
                "link": reverse_lazy("admin:staff_staff_changelist"),
                "permission": _view_perm("staff", "staff"),
            },
            {
                "title": "Teachers",
                "icon": "cast_for_education",
                "link": reverse_lazy("admin:staff_teacher_changelist"),
                "permission": _view_perm("staff", "teacher"),
            },
        ],
    },
    {
        "title": "Parents",
        "items": [
            {
                "title": "Guardians",
                "icon": "family_restroom",
                "link": reverse_lazy("admin:parents_guardian_changelist"),
                "permission": _view_perm("parents", "guardian"),
            },
            {
                "title": "Guardian students",
                "icon": "diversity_1",
                "link": reverse_lazy("admin:parents_guardianstudent_changelist"),
                "permission": _view_perm("parents", "guardianstudent"),
            },
        ],
    },
    {
        "title": "Academics",
        "items": [
            {
                "title": "Class levels",
                "icon": "stairs",
                "link": reverse_lazy("admin:academics_classlevel_changelist"),
                "permission": _view_perm("academics", "classlevel"),
            },
            {
                "title": "Class arms",
                "icon": "meeting_room",
                "link": reverse_lazy("admin:academics_classarm_changelist"),
                "permission": _view_perm("academics", "classarm"),
            },
            {
                "title": "Subjects",
                "icon": "menu_book",
                "link": reverse_lazy("admin:academics_subject_changelist"),
                "permission": _view_perm("academics", "subject"),
            },
            {
                "title": "Class subjects",
                "icon": "auto_stories",
                "link": reverse_lazy("admin:academics_classsubject_changelist"),
                "permission": _view_perm("academics", "classsubject"),
            },
            {
                "title": "Enrollments",
                "icon": "how_to_reg",
                "link": reverse_lazy("admin:academics_enrollment_changelist"),
                "permission": _view_perm("academics", "enrollment"),
            },
        ],
    },
    {
        "title": "Attendance",
        "items": [
            {
                "title": "Attendance",
                "icon": "event_available",
                "link": reverse_lazy("admin:attendance_attendance_changelist"),
                "permission": _view_perm("attendance", "attendance"),
            },
            {
                "title": "Attendance audit",
                "icon": "fact_check",
                "link": reverse_lazy("admin:attendance_attendanceaudit_changelist"),
                "permission": _view_perm("attendance", "attendanceaudit"),
            },
        ],
    },
    {
        "title": "Timetable",
        "items": [
            {
                "title": "Rooms",
                "icon": "meeting_room",
                "link": reverse_lazy("admin:timetable_room_changelist"),
                "permission": _view_perm("timetable", "room"),
            },
            {
                "title": "Periods",
                "icon": "schedule",
                "link": reverse_lazy("admin:timetable_period_changelist"),
                "permission": _view_perm("timetable", "period"),
            },
            {
                "title": "Timetable slots",
                "icon": "calendar_view_week",
                "link": reverse_lazy("admin:timetable_timetableslot_changelist"),
                "permission": _view_perm("timetable", "timetableslot"),
            },
        ],
    },
    {
        "title": "Examinations",
        "items": [
            {
                "title": "Grading schemes",
                "icon": "rule_settings",
                "link": reverse_lazy("admin:examinations_gradingscheme_changelist"),
                "permission": _view_perm("examinations", "gradingscheme"),
            },
            {
                "title": "Grade bands",
                "icon": "grading",
                "link": reverse_lazy("admin:examinations_gradeband_changelist"),
                "permission": _view_perm("examinations", "gradeband"),
            },
            {
                "title": "Exams",
                "icon": "edit_note",
                "link": reverse_lazy("admin:examinations_exam_changelist"),
                "permission": _view_perm("examinations", "exam"),
            },
            {
                "title": "Exam schedules",
                "icon": "event",
                "link": reverse_lazy("admin:examinations_examschedule_changelist"),
                "permission": _view_perm("examinations", "examschedule"),
            },
            {
                "title": "Invigilators",
                "icon": "visibility",
                "link": reverse_lazy("admin:examinations_invigilator_changelist"),
                "permission": _view_perm("examinations", "invigilator"),
            },
            {
                "title": "Assessments",
                "icon": "assignment",
                "link": reverse_lazy("admin:examinations_assessment_changelist"),
                "permission": _view_perm("examinations", "assessment"),
            },
            {
                "title": "Results",
                "icon": "checklist",
                "link": reverse_lazy("admin:examinations_result_changelist"),
                "permission": _view_perm("examinations", "result"),
            },
            {
                "title": "Result workflow history",
                "icon": "history_edu",
                "link": reverse_lazy("admin:examinations_resultworkflowstate_changelist"),
                "permission": _view_perm("examinations", "resultworkflowstate"),
            },
            {
                "title": "Report cards",
                "icon": "description",
                "link": reverse_lazy("admin:examinations_reportcard_changelist"),
                "permission": _view_perm("examinations", "reportcard"),
            },
        ],
    },
    {
        "title": "Finance",
        "items": [
            {
                "title": "Fee structures",
                "icon": "receipt_long",
                "link": reverse_lazy("admin:finance_feestructure_changelist"),
                "permission": _view_perm("finance", "feestructure"),
            },
            {
                "title": "Fee items",
                "icon": "sell",
                "link": reverse_lazy("admin:finance_feeitem_changelist"),
                "permission": _view_perm("finance", "feeitem"),
            },
            {
                "title": "Discounts",
                "icon": "percent",
                "link": reverse_lazy("admin:finance_discount_changelist"),
                "permission": _view_perm("finance", "discount"),
            },
            {
                "title": "Scholarships",
                "icon": "school",
                "link": reverse_lazy("admin:finance_scholarship_changelist"),
                "permission": _view_perm("finance", "scholarship"),
            },
            {
                "title": "Invoices",
                "icon": "request_quote",
                "link": reverse_lazy("admin:finance_invoice_changelist"),
                "permission": _view_perm("finance", "invoice"),
            },
            {
                "title": "Invoice lines",
                "icon": "list_alt",
                "link": reverse_lazy("admin:finance_invoiceline_changelist"),
                "permission": _view_perm("finance", "invoiceline"),
            },
            {
                "title": "Payments",
                "icon": "payments",
                "link": reverse_lazy("admin:finance_payment_changelist"),
                "permission": _view_perm("finance", "payment"),
            },
            {
                "title": "Refunds",
                "icon": "currency_exchange",
                "link": reverse_lazy("admin:finance_refund_changelist"),
                "permission": _view_perm("finance", "refund"),
            },
            {
                "title": "Receipts",
                "icon": "receipt",
                "link": reverse_lazy("admin:finance_receipt_changelist"),
                "permission": _view_perm("finance", "receipt"),
            },
            {
                "title": "Ledger entries",
                "icon": "account_balance",
                "link": reverse_lazy("admin:finance_ledgerentry_changelist"),
                "permission": _view_perm("finance", "ledgerentry"),
            },
        ],
    },
]
