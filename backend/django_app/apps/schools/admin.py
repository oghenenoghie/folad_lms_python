from django.contrib import admin

from .models import AcademicYear, Campus, Department, School, Term

admin.site.register(School)
admin.site.register(Campus)
admin.site.register(AcademicYear)
admin.site.register(Term)
admin.site.register(Department)
