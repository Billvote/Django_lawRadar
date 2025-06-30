from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

User = get_user_model()

# ─────────────────────────────────────────────
# 1. 회원가입 · 로그인
# ─────────────────────────────────────────────
class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(label="이메일", required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    # 이메일 중복 체크
    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("이미 사용 중인 이메일입니다.")
        return email

    # 이메일 저장
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class CustomAuthenticationForm(AuthenticationForm):
    pass


# ─────────────────────────────────────────────
# 2. 사이트 내부 즉시 비밀번호 재설정
# ─────────────────────────────────────────────
class DirectPasswordResetForm(forms.Form):
    email         = forms.EmailField(label="가입 이메일")
    new_password1 = forms.CharField(label="새 비밀번호", widget=forms.PasswordInput)
    new_password2 = forms.CharField(label="새 비밀번호 확인", widget=forms.PasswordInput)

    #
    # ① 이메일 필드 검증
    #
    def clean_email(self):
        """가입된 이메일인지 확인해 self.user_instance 에 보관"""
        email = self.cleaned_data["email"].strip()
        try:
            self.user_instance = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            self.user_instance = None
            raise forms.ValidationError("해당 이메일로 가입한 사용자가 없습니다.")
        return email

    #
    # ② 폼 전역 검증
    #
    def clean(self):
        cleaned = super().clean()

        # 이메일에 이미 오류가 있으면 나머지 검증은 건너뜀
        if self.errors.get("email"):
            return cleaned

        p1 = cleaned.get("new_password1")
        p2 = cleaned.get("new_password2")

        # 비밀번호 일치 여부
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("비밀번호가 일치하지 않습니다.")

        # 비밀번호 유효성(Django 기본 정책) 검사
        if p1 and self.user_instance:
            try:
                validate_password(p1, self.user_instance)
            except ValidationError as e:
                self.add_error("new_password1", e)

        return cleaned

    #
    # ③ 저장
    #
    def save(self, commit=True):
        """
        email·password 검증이 모두 끝난 뒤 호출된다.
        self.user_instance 는 clean_email() 단계에서 이미 확보돼 있음.
        """
        user = getattr(self, "user_instance", None)
        if not user:
            raise RuntimeError("save() 호출 전에 clean() 이 올바르게 실행되지 않았습니다.")

        user.set_password(self.cleaned_data["new_password1"])
        if commit:
            user.save()
        return user
