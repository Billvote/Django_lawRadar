from .models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm

# 회원가입
class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'password1', 'password2')

# 로그인
class CustomAuthenticationForm(AuthenticationForm):
    pass