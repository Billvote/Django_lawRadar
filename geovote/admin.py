from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from .models import District, Member
# from .models import Member, Party

@admin.register(Member)
class MemberAdmin(ImportExportModelAdmin):
    pass

@admin.register(District)
class DistrictAdmin(ImportExportModelAdmin):
    pass