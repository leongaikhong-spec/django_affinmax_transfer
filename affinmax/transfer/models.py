from django.db import models



class TransferList(models.Model):
    group_id = models.CharField(max_length=50)
    tran_id = models.CharField(max_length=50, unique=True)
    amount = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    bene_acc_no = models.CharField(max_length=30)
    bene_name = models.CharField(max_length=100)
    bank_code = models.CharField(max_length=20)
    recRef = models.CharField(max_length=100)
    #status = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=20)
    class Meta:
        db_table = "transfer_list"

    def __str__(self):
        return f"{self.tran_id} - {self.bene_name}"


# 新增 MobileList 模型，独立出来
class MobileList(models.Model):
    phone_number = models.CharField(max_length=20, unique=True)
    is_online = models.BooleanField(default=False)
    is_activated = models.BooleanField(default=False)
    is_busy = models.BooleanField(default=False)
    last_error = models.TextField(null=True, blank=True)
    current_balance = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    corp_id = models.CharField(max_length=50, null=True, blank=True)
    user_id = models.CharField(max_length=50, null=True, blank=True)
    password = models.CharField(max_length=100, null=True, blank=True)
    tran_pass = models.CharField(max_length=100, null=True, blank=True)
    log_file = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "mobile_list"

    def __str__(self):
        return f"{self.phone_number}"


