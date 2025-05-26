from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from .models import Party, District
# from .models import Member, Party

@admin.register(Party)
class PartyAdmin(ImportExportModelAdmin):
    pass

@admin.register(District)
class DistrictAdmin(ImportExportModelAdmin):
    pass