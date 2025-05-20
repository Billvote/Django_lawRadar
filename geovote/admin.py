from django.contrib import admin
from .models import Member, District, Party, Committee, Bill, Vote

admin.site.register(Member)
admin.site.register(District)
admin.site.register(Party)
admin.site.register(Committee)
admin.site.register(Bill)
admin.site.register(Vote)