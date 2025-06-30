# accounts/validators.py
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import (
    UserAttributeSimilarityValidator,
    MinimumLengthValidator,
    CommonPasswordValidator,
    NumericPasswordValidator,
)
from django.utils.translation import gettext_lazy as _


# ─────────────────────────────────────────────
# ① 개인정보와의 유사성 검사
# ─────────────────────────────────────────────
class MySimilarityValidator(UserAttributeSimilarityValidator):
    def validate(self, password, user=None):
        # 기본 로직 그대로 사용
        super().validate(password, user)

    def get_help_text(self):
        return _("- 개인정보와 비슷합니다. 다른 조합으로 변경해 주세요.")


# ─────────────────────────────────────────────
# ② 최소 길이 검사
# ─────────────────────────────────────────────
class MyMinLengthValidator(MinimumLengthValidator):
    def __init__(self, min_length=8):
        self.min_length = int(min_length)

    def validate(self, password, user=None):
        if len(password) < self.min_length:
            raise ValidationError(
                _("- %(min_length)d자 이상으로 입력해 주세요")
                % {"min_length": self.min_length},
                code="password_too_short",
            )

    def get_help_text(self):
        return _("- %(min_length)d자 이상으로 입력해 주세요") % {
            "min_length": self.min_length
        }


# ─────────────────────────────────────────────
# ③ 흔한 비밀번호 검사
# ─────────────────────────────────────────────
class MyCommonValidator(CommonPasswordValidator):
    def validate(self, password, user=None):
        """
        CommonPasswordValidator.validate() 가 ValidationError 를
        발생시키면 한국어 메시지로 교체해 다시 raise.
        """
        try:
            super().validate(password, user)
        except ValidationError:
            raise ValidationError(
                _("- 자주 쓰이는 비밀번호입니다. 새로 만들어 주세요."),
                code="password_too_common",
            )

    def get_help_text(self):
        return _("- 자주 쓰이는 비밀번호입니다. 새로 만들어 주세요.")


# ─────────────────────────────────────────────
# ④ 숫자만으로 된 비밀번호 검사
# ─────────────────────────────────────────────
class MyNumericValidator(NumericPasswordValidator):
    def validate(self, password, user=None):
        if password.isdigit():
            raise ValidationError(
                _("- 숫자만으로는 안전하지 않습니다. 문자나 기호도 넣어 주세요."),
                code="password_entirely_numeric",
            )

    def get_help_text(self):
        return _("- 숫자만으로는 안전하지 않습니다. 문자나 기호도 넣어 주세요.")
