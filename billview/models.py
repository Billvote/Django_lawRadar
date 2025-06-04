# billview/models.py
from django.db import models

class Bill(models.Model):
    title = models.CharField(max_length=200)  # 의안명
    label = models.CharField(max_length=100)  # 관련 법안 그룹 라벨
    content = models.TextField()  # 의안 내용
    created_date = models.DateTimeField(auto_now_add=True)
    # 기타 필요한 필드들
    
    def __str__(self):
        return self.title
