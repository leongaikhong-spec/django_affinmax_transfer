from django.contrib import admin
from .models import TransferList, MobileList, TransferGroupList
# TransferGroupList 后台
@admin.register(TransferGroupList)
class TransferGroupListAdmin(admin.ModelAdmin):
    list_display = ("total_tran", "total_tran_amount", "success_tran_amount", "current_balance", "created_at", "updated_at")
    search_fields = ("total_tran",)

# TransferList 后台
@admin.register(TransferList)
class TransferListAdmin(admin.ModelAdmin):
    list_display = ("tran_id", "group_id", "amount", "bene_acc_no", "bene_name", "bank_code", "recRef", "phone_number", "status", "complete_date", "updated_at", "error_message")
    search_fields = ("tran_id", "bene_name", "phone_number")

# MobileList 后台
@admin.register(MobileList)
class MobileListAdmin(admin.ModelAdmin):
    list_display = ("device", "is_online", "is_activated", "is_busy", "current_balance", "corp_id", "user_id", "created_at", "updated_at")
    search_fields = ("device", "corp_id", "user_id")
