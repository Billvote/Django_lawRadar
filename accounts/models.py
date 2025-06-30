from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser
from billview.models import Bill

# user 모델
class User(AbstractUser):
    pass

# 좋아요 관계 저장
class BillLike(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'bill')  # 중복 방지