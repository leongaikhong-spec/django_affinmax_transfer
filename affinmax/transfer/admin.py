from django.contrib import admin
from .models import TransferList

# Register your models here.

@admin.register(TransferList)
class TransferListAdmin(admin.ModelAdmin):
    list_display = ("tran_id", "amount", "bene_acc_no", "bene_name", "bank_code", "recRef")
    search_fields = ("tran_id", "bene_name")
