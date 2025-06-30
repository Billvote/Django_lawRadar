from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser

from billview.models import Bill
from geovote.models import Member


class User(AbstractUser):
    """
    별도 커스텀 필드 없이 Django 기본 AbstractUser만 사용
    """
    def __str__(self):
        return self.username


# ─────────────────────────────────────────────
#  좋아요 모델
# ─────────────────────────────────────────────
class BillLike(models.Model):
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    bill       = models.ForeignKey(Bill, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "bill")
        verbose_name           = "법안 좋아요"
        verbose_name_plural    = "법안 좋아요 목록"


class MemberLike(models.Model):
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    member     = models.ForeignKey(Member, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together     = ("user", "member")
        verbose_name        = "의원 좋아요"
        verbose_name_plural = "의원 좋아요 목록"

    def __str__(self):
        return f"{self.user.username} likes {self.member.name}"
