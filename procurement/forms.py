from django import forms
from .models import CostingSheetLineItem


class LineItemForm(forms.ModelForm):
    class Meta:
        model = CostingSheetLineItem
        fields = [
            "description", "unit", "quantity",
            "provider_1_name", "provider_1_amount", "provider_1_currency",
            "provider_2_name", "provider_2_amount", "provider_2_currency",
            "provider_3_name", "provider_3_amount", "provider_3_currency",
            "selected_provider",
        ]
        widgets = {
            "description": forms.TextInput(attrs={"class": "form-control"}),
            "unit": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. days, units"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "provider_1_name": forms.TextInput(attrs={"class": "form-control"}),
            "provider_1_amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "provider_1_currency": forms.TextInput(attrs={"class": "form-control", "placeholder": "ZAR"}),
            "provider_2_name": forms.TextInput(attrs={"class": "form-control"}),
            "provider_2_amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "provider_2_currency": forms.TextInput(attrs={"class": "form-control", "placeholder": "ZAR"}),
            "provider_3_name": forms.TextInput(attrs={"class": "form-control"}),
            "provider_3_amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "provider_3_currency": forms.TextInput(attrs={"class": "form-control", "placeholder": "ZAR"}),
            "selected_provider": forms.Select(attrs={"class": "form-select"}),
        }

    def clean(self):
        cleaned = super().clean()
        for i in range(1, 4):
            name = cleaned.get(f"provider_{i}_name", "").strip()
            amount = cleaned.get(f"provider_{i}_amount")
            currency = cleaned.get(f"provider_{i}_currency", "").strip()
            if name and (not amount or not currency):
                self.add_error(
                    f"provider_{i}_amount" if not amount else f"provider_{i}_currency",
                    f"Amount and currency are required when Provider {i} name is provided."
                )
        return cleaned


class RejectForm(forms.Form):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        label="Rejection Reason",
    )


class DirectorApproveForm(forms.Form):
    justification = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        label="Justification (required if negotiated amounts exceed approved amounts)",
    )


class ReviseQuoteForm(forms.Form):
    line_item_id = forms.IntegerField(widget=forms.HiddenInput)
    amount = forms.DecimalField(
        max_digits=14, decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"})
    )
    currency = forms.CharField(
        max_length=3,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "ZAR"})
    )


class POCancelForm(forms.Form):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        label="Cancellation Reason",
    )


class ETAForm(forms.Form):
    eta_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        label="Supplier ETA Date",
    )


class DeliveryForm(forms.Form):
    delivery_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        label="Actual Delivery Date",
    )
