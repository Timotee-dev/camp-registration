from django import forms
from django.contrib.auth import authenticate, get_user_model, password_validation
from django.contrib.auth.forms import PasswordChangeForm

User = get_user_model()


class SignupForm(forms.Form):
    full_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"autocomplete": "name", "autofocus": True}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
                               help_text="At least 8 characters, not too common.")

    def clean_full_name(self):
        name = " ".join(self.cleaned_data["full_name"].split())
        if len(name) < 2:
            raise forms.ValidationError("Please enter your name.")
        return name

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists. Try logging in.")
        return email

    def clean(self):
        data = super().clean()
        if data.get("password") and data.get("email"):
            temp = User(username=data["email"], email=data["email"], first_name=data.get("full_name", ""))
            try:
                password_validation.validate_password(data["password"], temp)
            except forms.ValidationError as e:
                self.add_error("password", e)
        return data

    def save(self):
        d = self.cleaned_data
        return User.objects.create_user(username=d["email"], email=d["email"], password=d["password"],
                                        first_name=d["full_name"])


class LoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"autocomplete": "email", "autofocus": True}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        if data.get("email") and data.get("password"):
            self.user = authenticate(self.request, username=data["email"], password=data["password"])
            if self.user is None:
                raise forms.ValidationError("Incorrect email or password.")
        return data


class ProfileForm(forms.Form):
    full_name = forms.CharField(max_length=150)
    email = forms.EmailField()

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        clash = User.objects.exclude(pk=self.user.pk).filter(email__iexact=email).exists() \
            or User.objects.exclude(pk=self.user.pk).filter(username__iexact=email).exists()
        if clash:
            raise forms.ValidationError("Another account already uses this email.")
        return email

    def save(self):
        u = self.user
        u.first_name = " ".join(self.cleaned_data["full_name"].split())
        u.email = u.username = self.cleaned_data["email"]
        u.save(update_fields=["first_name", "email", "username"])
        return u


class StyledPasswordChangeForm(PasswordChangeForm):
    pass
