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
    status = models.IntegerField(default=0, db_column='status_id')
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


class APICallLog(models.Model):
    method = models.CharField(max_length=10)  # GET, POST, PUT, DELETE, etc.
    path = models.CharField(max_length=500)  # API路径，例如 script/make_transactions/
    request_body = models.TextField(null=True, blank=True)  # 请求体JSON
    response_body = models.TextField(null=True, blank=True)  # 响应体JSON
    client_ip = models.GenericIPAddressField()  # 客户端IP地址
    status_code = models.IntegerField()  # HTTP状态码，例如 200, 404, 500
    timestamp = models.DateTimeField(auto_now_add=True)  # 记录时间
    user_agent = models.TextField(null=True, blank=True)  # 浏览器/客户端信息
    response_time = models.FloatField(null=True, blank=True)  # 响应时间（毫秒）
    
    class Meta:
        db_table = "api_call_log"
        ordering = ['-timestamp']  # 默认按时间倒序排列
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['path']),
            models.Index(fields=['client_ip']),
            models.Index(fields=['status_code']),
        ]
    
    def __str__(self):
        return f"{self.method} {self.path} - {self.status_code} at {self.timestamp}"


class CallbackLog(models.Model):
    callback_url = models.CharField(max_length=500)  # Callback的目标URL
    request_body = models.TextField(null=True, blank=True)  # 发送给callback的请求体
    response_body = models.TextField(null=True, blank=True)  # Callback返回的响应体
    status_code = models.IntegerField(null=True, blank=True)  # Callback的HTTP状态码
    created_at = models.DateTimeField(auto_now_add=True)  # 记录时间
    success = models.BooleanField(default=True)  # Callback是否成功
    error_message = models.TextField(null=True, blank=True)  # 错误信息（如果失败）
    
    class Meta:
        db_table = "callback_log"
        ordering = ['-created_at']  # 默认按时间倒序排列
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['callback_url']),
            models.Index(fields=['success']),
        ]
    
    def __str__(self):
        return f"Callback to {self.callback_url} at {self.created_at}"


