from django import forms
from django.core.exceptions import ValidationError

from trf.models import TRFRequest
from projects.models import Project

from .models import PurchaseOrder
from .payment_models import PaymentRequisition


class PaymentRequisitionForm(forms.ModelForm):
    trf = forms.ModelChoiceField(
        queryset=TRFRequest.objects.filter(status=TRFRequest.Status.APPROVED),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Approved TRF",
    )
    project = forms.ModelChoiceField(
        queryset=Project.objects.filter(status=Project.Status.ACTIVE),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Active Project",
    )
    purchase_order = forms.ModelChoiceField(
        queryset=PurchaseOrder.objects.filter(status=PurchaseOrder.Status.FULFILLED),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Fulfilled Purchase Order",
    )

    class Meta:
        model = PaymentRequisition
        fields = [
            "requisition_type",
            "amount",
            "currency",
            "description",
            "trf",
            "project",
            "purchase_order",
        ]
        widgets = {
            "requisition_type": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "currency": forms.TextInput(attrs={"class": "form-control", "placeholder": "ZAR"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }

    def clean(self):
        cleaned = super().clean()
        trf = cleaned.get("trf")
        project = cleaned.get("project")
        purchase_order = cleaned.get("purchase_order")
        selected = [value for value in (trf, project, purchase_order) if value]

        if len(selected) != 1:
            raise ValidationError("Exactly one of TRF, Project, or Purchase Order must be selected.")

        return cleaned


class PaymentRequisitionRejectForm(forms.Form):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
        label="Rejection Reason",
        required=True,
    )


class PaymentRequisitionPayForm(forms.Form):
    payment_reference = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=True,
        label="Payment Reference",
    )
    proof_of_payment = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
        label="Proof of Payment",
    )
