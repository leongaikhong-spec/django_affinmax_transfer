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
    status = models.CharField(max_length=20)
    class Meta:
        db_table = "transfer_list"

    def __str__(self):
        return f"{self.tran_id} - {self.bene_name}"


