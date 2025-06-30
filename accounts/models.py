from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser
from billview.models import Bill
from geovote.models import Member

# user 모델
class User(AbstractUser):
    pass

# 유저가 좋아하는 의안
class BillLike(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'bill')  # 중복 방지

# 유저가 좋아하는 국회의원
class MemberLike(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'member')  # 중복 좋아요 방지
        verbose_name = '의원 좋아요'
        verbose_name_plural = '의원 좋아요 목록'

    def __str__(self):
        return f"{self.user.username} likes {self.member.name}"