from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from .models import Region, Member
# from .models import Member, Party

@admin.register(Member)
class MemberAdmin(ImportExportModelAdmin):
    pass

@admin.register(Region)
class RegionAdmin(ImportExportModelAdmin):
    pass