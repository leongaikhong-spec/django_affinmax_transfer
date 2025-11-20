from django.contrib import admin
from .models import TransactionsList, MobileList, TransactionsGroupList, APICallLog, CallbackLog

# TransactionsGroupList 后台
@admin.register(TransactionsGroupList)
class TransactionsGroupListAdmin(admin.ModelAdmin):
    list_display = ("id", "total_tran_bene_acc", "total_tran_amount", "success_tran_amount", "current_balance", "created_at", "updated_at")
    search_fields = ("id", "total_tran_bene_acc", "total_tran_amount", "success_tran_amount", "current_balance", "created_at", "updated_at")

# TransactionsList 后台
@admin.register(TransactionsList)
class TransactionsListAdmin(admin.ModelAdmin):
    list_display = ("tran_id", "group_id", "amount", "bene_acc_no", "bene_name", "bank_code", "recRef", "phone_number", "status", "callback_status", "callback_attempts", "complete_date", "updated_at", "error_message")
    search_fields = ("tran_id", "group_id", "amount", "bene_acc_no", "bene_name", "bank_code", "recRef", "phone_number", "status", "callback_status", "callback_attempts", "complete_date", "updated_at", "error_message")
    list_filter = ("status", "callback_status", "bank_code")

# MobileList 后台
@admin.register(MobileList)
class MobileListAdmin(admin.ModelAdmin):
    list_display = ("device", "is_online", "is_activated", "is_busy", "current_balance", "corp_id", "user_id", "created_at", "updated_at")
    search_fields = ("device", "is_online", "is_activated", "is_busy", "current_balance", "corp_id", "user_id", "created_at", "updated_at",)
    readonly_fields = ("is_online",)


# APICallLog 后台
@admin.register(APICallLog)
class APICallLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "method", "path", "client_ip", "status_code", "response_time")
    list_filter = ("method", "status_code", "timestamp")
    search_fields = ("path", "client_ip", "request_body", "response_body")
    readonly_fields = ("method", "path", "request_body", "response_body", "client_ip", "status_code", "timestamp", "user_agent", "response_time")
    date_hierarchy = "timestamp"
    ordering = ("-timestamp",)
    
    # 禁止添加和修改
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


# CallbackLog 后台
@admin.register(CallbackLog)
class CallbackLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "callback_url", "status_code", "success")
    list_filter = ("success", "created_at", "status_code")
    search_fields = ("callback_url", "request_body", "response_body", "error_message")
    readonly_fields = ("callback_url", "request_body", "response_body", "status_code", "created_at", "success", "error_message")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    
    # 禁止添加和修改
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
