from django.db import models

class TransactionsStatus(models.Model):
    status_name = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = "transactions_status"

    def __str__(self):
        return self.status_name

class TransactionsGroupList(models.Model):
    total_tran_bene_acc = models.IntegerField(default=0)
    total_tran_amount = models.CharField(max_length=50)
    success_tran_amount = models.CharField(max_length=50)
    current_balance = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "transactions_group_list"

    def __str__(self):
        return f"Group {self.id} - {self.total_tran_bene_acc} transactions"


class TransactionsList(models.Model):
    group = models.ForeignKey('TransactionsGroupList', on_delete=models.CASCADE, db_column='group_id', related_name='transfers', null=True, blank=True)
    tran_id = models.CharField(max_length=50, unique=True)
    amount = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    bene_acc_no = models.CharField(max_length=30)
    bene_name = models.CharField(max_length=100)
    bank_code = models.CharField(max_length=20)
    recRef = models.CharField(max_length=100)
    status = models.CharField(max_length=20, default="pending")
    phone_number = models.CharField(max_length=20)
    complete_date = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    error_message = models.TextField(null=True, blank=True)
    class Meta:
        db_table = "transactions_list"

    def __str__(self):
        return f"{self.tran_id} - {self.bene_name}"


class MobileList(models.Model):
    device = models.CharField(max_length=20, unique=True)
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
        return f"{self.device}"


