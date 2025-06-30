# Django_lawRadar/accounts/models.py
from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser

from billview.models import Bill
from geovote.models import Member


class User(AbstractUser):
    """
    기본 User 모델을 확장해 닉네임을 추가한다.
    - username : 로그인 ID (기존 필드 그대로 사용)
    - nickname : 화면에 노출되는 별칭
    """
    nickname = models.CharField(
        "닉네임",
        max_length=30,
        unique=True,
        help_text="30자 이하, 공백 없이 입력",
    )

    def __str__(self):
        # 닉네임이 있으면 닉네임, 없으면 username
        return self.nickname or self.username


# ─────────────────────────────────────────────
#  좋아요 모델
# ─────────────────────────────────────────────
class BillLike(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "bill")  # 중복 좋아요 방지
        verbose_name = "법안 좋아요"
        verbose_name_plural = "법안 좋아요 목록"


class MemberLike(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "member")  # 중복 좋아요 방지
        verbose_name = "의원 좋아요"
        verbose_name_plural = "의원 좋아요 목록"

    def __str__(self):
        return f"{self.user.nickname or self.user.username} likes {self.member.name}"
