from django.db import models

class LogEntry(models.Model):
    phone_number = models.CharField(max_length=20)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.timestamp}] {self.phone_number}: {self.message[:30]}"
