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
    email = forms.EmailField(label='이메일', required=True)

    class Meta:
        model  = User
        fields = ('username', 'email', 'password1', 'password2')  # ← email 포함

    # 이메일 중복 체크
    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('이미 사용 중인 이메일입니다.')
        return email

    # 이메일 저장
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class CustomAuthenticationForm(AuthenticationForm):
    pass


# ─────────────────────────────────────────────
# 2. 사이트 내부 즉시 비밀번호 재설정
# ─────────────────────────────────────────────
class DirectPasswordResetForm(forms.Form):
    email          = forms.EmailField(label="가입 이메일")
    new_password1  = forms.CharField(label="새 비밀번호",       widget=forms.PasswordInput)
    new_password2  = forms.CharField(label="새 비밀번호 확인", widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data['email']
        try:
            self._user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise forms.ValidationError("해당 이메일로 가입한 사용자가 없습니다.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get('new_password1'), cleaned.get('new_password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("비밀번호가 일치하지 않습니다.")

        # 비밀번호 유효성 검사
        try:
            validate_password(p1, self._user)
        except ValidationError as e:
            self.add_error('new_password1', e)
        return cleaned

    def save(self, commit=True):
        self._user.set_password(self.cleaned_data['new_password1'])
        if commit:
            self._user.save()
        return self._user
