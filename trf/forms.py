from django import forms
from django.forms import inlineformset_factory

from .models import TRFRequest, Milestone, Expense


class TRFForm(forms.ModelForm):
    class Meta:
        model = TRFRequest
        fields = ["project_name", "training_start"]
        widgets = {
            "training_start": forms.DateInput(attrs={"type": "date"}),
        }


MilestoneFormSet = inlineformset_factory(
    TRFRequest,
    Milestone,
    fields=["name", "target_date"],
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
    widgets={
        "target_date": forms.DateInput(attrs={"type": "date"}),
    },
)

ExpenseFormSet = inlineformset_factory(
    TRFRequest,
    Expense,
    fields=["description", "amount", "currency"],
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
