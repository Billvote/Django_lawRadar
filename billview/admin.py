from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from .models import Bill

# admin.site.register(Bill)

@admin.register(Bill)
class BillAdmin(ImportExportModelAdmin):
    pass