# Django_lawRadar/accounts/forms.py
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
        model  = User
        fields = ("username", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exists():
            raise ValidationError("이미 사용 중인 이메일입니다.")
        return email

    def save(self, commit=True):
        user       = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class CustomAuthenticationForm(AuthenticationForm):
    """username + password 로그인 (기본)"""
    pass


# ─────────────────────────────────────────────
# 2. 비밀번호 즉시 재설정  (아이디 입력 방식)
# ─────────────────────────────────────────────
class DirectPasswordResetForm(forms.Form):
    username      = forms.CharField(label="아이디", max_length=150)
    new_password1 = forms.CharField(label="새 비밀번호", widget=forms.PasswordInput)
    new_password2 = forms.CharField(label="새 비밀번호 확인", widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        try:
            self.user_instance = User.objects.get(username=username, is_active=True)
        except User.DoesNotExist:
            self.user_instance = None
            raise ValidationError("해당 아이디로 가입한 사용자가 없습니다.")
        return username

    def clean(self):
        cleaned = super().clean()

        if self.errors.get("username"):
            return cleaned

        p1, p2 = cleaned.get("new_password1"), cleaned.get("new_password2")

        if p1 and p2 and p1 != p2:
            raise ValidationError("비밀번호가 일치하지 않습니다.")

        if p1 and self.user_instance:
            try:
                validate_password(p1, self.user_instance)
            except ValidationError as e:
                self.add_error("new_password1", e)

        return cleaned

    def save(self, commit=True):
        user = getattr(self, "user_instance", None)
        if not user:
            raise RuntimeError("save() 호출 전에 clean() 이 올바르게 실행되지 않았습니다.")

        user.set_password(self.cleaned_data["new_password1"])
        if commit:
            user.save()
        return user


# ─────────────────────────────────────────────
# 3. 사용자 이름(username) 수정 폼
# ─────────────────────────────────────────────
class UpdateUsernameForm(forms.ModelForm):
    username = forms.CharField(
        label="새 사용자 이름",
        max_length=150,
        help_text="영문자·숫자·@/./+/-/_ 조합, 150자 이하",
    )

    class Meta:
        model  = User
        fields = ("username",)

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if (
            User.objects.filter(username=username)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise ValidationError("이미 사용 중인 사용자 이름입니다.")
        return username


# ─────────────────────────────────────────────
# 4. 이메일로 아이디 찾기 폼  ★ 추가
# ─────────────────────────────────────────────
class FindUsernameForm(forms.Form):
    email = forms.EmailField(label="가입 이메일")

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        try:
            self.user_instance = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            self.user_instance = None
            raise ValidationError("해당 이메일로 가입한 아이디가 없습니다.")
        return email

    def get_username(self):
        """
        clean_email() 단계에서 확보해 둔 user_instance 의 username 반환
        view 에서 form.get_username() 으로 즉시 사용 가능
        """
        if not getattr(self, "user_instance", None):
            raise RuntimeError("clean_email() 검증이 끝난 뒤에만 호출하세요.")
        return self.user_instance.username
