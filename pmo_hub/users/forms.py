from django import (
    forms,
    imports,  # noqa: F401
)

from .models import Profile


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["image"]
