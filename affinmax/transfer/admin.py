from django.contrib import admin
from .models import LogEntry

@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ("phone_number", "message", "timestamp")  # 列表页显示字段
    list_filter = ("phone_number", "timestamp")              # 右侧过滤器
    search_fields = ("phone_number", "message")              # 搜索框
