from django.db import models

# Create your models here.

# bill
class Bill(models.Model):
    bill_id = models.CharField(max_length=50, unique=True)  # 법안 고유 ID
    description = models.TextField(blank=True, null=True)  # 법안 설명 전체 텍스트
    
    def __str__(self):
        return self.bill_id