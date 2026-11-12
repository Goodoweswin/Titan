import unicodedata

from django import forms
from django.contrib.auth.password_validation import validate_password


def clean_name(value):
    if not isinstance(value, str):
        raise forms.ValidationError("昵称必须是文字。")
    value = value.strip()
    if not 1 <= len(value) <= 60 or any(
        unicodedata.category(ch).startswith("C") for ch in value
    ):
        raise forms.ValidationError("昵称需为1至60个字符，不能包含控制字符。")
    return value


class RegistrationForm(forms.Form):
    email = forms.EmailField(label="邮箱", max_length=254)
    name = forms.CharField(label="昵称", max_length=60)
    password = forms.CharField(label="密码", widget=forms.PasswordInput, strip=False, max_length=1024)

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean_name(self):
        return clean_name(self.cleaned_data["name"])

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password


class LoginForm(forms.Form):
    email = forms.EmailField(label="邮箱", max_length=254)
    password = forms.CharField(label="密码", widget=forms.PasswordInput, strip=False, max_length=1024)


class EmailForm(forms.Form):
    email = forms.EmailField(label="邮箱", max_length=254)


class ResetForm(forms.Form):
    password = forms.CharField(label="密码", widget=forms.PasswordInput, strip=False, max_length=1024)

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password
