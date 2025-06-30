# accounts/forms.py
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
    email    = forms.EmailField(label="이메일", required=True)
    nickname = forms.CharField(
        label="닉네임",
        max_length=30,
        help_text="30자 이하 · 공백 없이 입력",
    )

    class Meta:
        model  = User
        fields = (
            "username",   # 로그인 ID
            "nickname",   # 닉네임
            "email",
            "password1",
            "password2",
        )

    # 이메일 중복 체크
    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("이미 사용 중인 이메일입니다.")
        return email

    # 닉네임 중복 체크
    def clean_nickname(self):
        nickname = self.cleaned_data["nickname"]
        if User.objects.filter(nickname=nickname).exists():
            raise forms.ValidationError("이미 사용 중인 닉네임입니다.")
        return nickname

    # 저장
    def save(self, commit=True):
        user          = super().save(commit=False)
        user.email    = self.cleaned_data["email"]
        user.nickname = self.cleaned_data["nickname"]
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

    # ① 이메일 검증
    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        try:
            self.user_instance = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            self.user_instance = None
            raise forms.ValidationError("해당 이메일로 가입한 사용자가 없습니다.")
        return email

    # ② 전체 폼 검증
    def clean(self):
        cleaned = super().clean()

        # 이메일 오류가 있으면 나머지 검증 패스
        if self.errors.get("email"):
            return cleaned

        p1 = cleaned.get("new_password1")
        p2 = cleaned.get("new_password2")

        # 비밀번호 일치 여부
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("비밀번호가 일치하지 않습니다.")

        # 비밀번호 유효성 검사
        if p1 and self.user_instance:
            try:
                validate_password(p1, self.user_instance)
            except ValidationError as e:
                self.add_error("new_password1", e)

        return cleaned

    # ③ 저장
    def save(self, commit=True):
        user = getattr(self, "user_instance", None)
        if not user:
            raise RuntimeError("save() 호출 전에 clean() 이 올바르게 실행되지 않았습니다.")

        user.set_password(self.cleaned_data["new_password1"])
        if commit:
            user.save()
        return user


# ─────────────────────────────────────────────
# 3. 닉네임 수정 폼
# ─────────────────────────────────────────────
class UpdateNicknameForm(forms.ModelForm):
    """
    로그인 방식(일반 · 소셜)과 무관하게
    현재 사용자 본인의 닉네임을 변경하기 위한 단순 ModelForm
    """

    nickname = forms.CharField(
        label="닉네임",
        max_length=30,
        help_text="30자 이하 · 공백 없이 입력",
    )

    class Meta:
        model  = User
        fields = ("nickname",)

    # 중복 닉네임 방지
    def clean_nickname(self):
        nickname = self.cleaned_data["nickname"].strip()
        qs = User.objects.filter(nickname=nickname).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("이미 사용 중인 닉네임입니다.")
        return nickname
