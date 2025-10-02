from django.contrib import admin
from .models import TransferList, MobileList

# Register your models here.


# TransferList 后台
@admin.register(TransferList)
class TransferListAdmin(admin.ModelAdmin):
    list_display = ("tran_id", "amount", "bene_acc_no", "bene_name", "bank_code", "recRef", "phone_number", "group_id")
    search_fields = ("tran_id", "bene_name", "phone_number")

# MobileList 后台
@admin.register(MobileList)
class MobileListAdmin(admin.ModelAdmin):
    list_display = ("phone_number", "is_online", "is_activated", "is_busy", "current_balance", "corp_id", "user_id", "created_at", "updated_at")
    search_fields = ("phone_number", "corp_id", "user_id")
