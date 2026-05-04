from django import forms
from .models import Milestone, Project

# Currency choices for dropdown
CURRENCY_CHOICES = [
    ('USD', 'USD - US Dollar'),
    ('EUR', 'EUR - Euro'),
    ('GBP', 'GBP - British Pound'),
    ('ZAR', 'ZAR - South African Rand'),
    ('CAD', 'CAD - Canadian Dollar'),
    ('AUD', 'AUD - Australian Dollar'),
    ('JPY', 'JPY - Japanese Yen'),
    ('CNY', 'CNY - Chinese Yuan'),
    ('INR', 'INR - Indian Rupee'),
    ('BRL', 'BRL - Brazilian Real'),
    ('MXN', 'MXN - Mexican Peso'),
    ('CHF', 'CHF - Swiss Franc'),
    ('NZD', 'NZD - New Zealand Dollar'),
    ('SGD', 'SGD - Singapore Dollar'),
    ('HKD', 'HKD - Hong Kong Dollar'),
    ('SEK', 'SEK - Swedish Krona'),
    ('NOK', 'NOK - Norwegian Krone'),
    ('DKK', 'DKK - Danish Krone'),
    ('PLN', 'PLN - Polish Zloty'),
    ('TRY', 'TRY - Turkish Lira'),
    ('AED', 'AED - UAE Dirham'),
    ('SAR', 'SAR - Saudi Riyal'),
    ('EGP', 'EGP - Egyptian Pound'),
    ('NGN', 'NGN - Nigerian Naira'),
    ('KES', 'KES - Kenyan Shilling'),
]

class MilestoneForm(forms.ModelForm):
    currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = Milestone
        fields = ['name', 'target_date', 'description', 'status', 'is_trf_expense', 'cost_amount', 'currency']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter milestone name'}),
            'target_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Optional description'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'is_trf_expense': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'cost_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set initial currency from instance if exists
        if self.instance and self.instance.pk and self.instance.currency:
            self.fields['currency'].initial = self.instance.currency
        else:
            self.fields['currency'].initial = 'USD'


class ProjectStatusForm(forms.Form):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('On_Hold', 'On Hold'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]
    
    new_status = forms.ChoiceField(choices=STATUS_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))
    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Optional reason for status change'}))
    confirmed = forms.BooleanField(required=False, initial=False, widget=forms.HiddenInput())