from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from .models import Member

@admin.register(Member)
class MemberAdmin(ImportExportModelAdmin):
    pass