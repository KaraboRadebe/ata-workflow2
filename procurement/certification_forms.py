from django import forms
from django.core.exceptions import ValidationError

from .models import Certification


class CertificationForm(forms.ModelForm):
    class Meta:
        model = Certification
        fields = [
            "contact",
            "certification_type",
            "issue_date",
            "expiry_date",
        ]
        widgets = {
            "contact": forms.Select(attrs={"class": "form-select"}),
            "certification_type": forms.Select(attrs={"class": "form-select"}),
            "issue_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "expiry_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }

    def clean(self):
        cleaned = super().clean()
        issue_date = cleaned.get("issue_date")
        expiry_date = cleaned.get("expiry_date")

        if issue_date and expiry_date and expiry_date <= issue_date:
            raise ValidationError("Expiry date must be after issue date.")

        return cleaned
