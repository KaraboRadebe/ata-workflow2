import uuid
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import models


class CostingSheet(models.Model):
    class Status(models.TextChoices):
        DRAFT                  = "Draft", "Draft"
        SUBMITTED              = "Submitted", "Submitted"
        CDR_APPROVED           = "CDR_Approved", "CDR Approved"
        CDR_REJECTED           = "CDR_Rejected", "CDR Rejected"
        NEGOTIATING            = "Negotiating", "Negotiating"
        SUBMITTED_FOR_DIRECTOR = "Submitted_For_Director", "Submitted for Director"
        DIRECTOR_APPROVED      = "Director_Approved", "Director Approved"
        DIRECTOR_REJECTED      = "Director_Rejected", "Director Rejected"

    project  = models.OneToOneField(
        "projects.Project", on_delete=models.PROTECT, related_name="costing_sheet"
    )
    status   = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
    pdr      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="costing_sheets_as_pdr"
    )
    cdr      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="costing_sheets_as_cdr", null=True, blank=True
    )
    director = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="costing_sheets_as_director", null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"CS for {self.project.name} [{self.status}]"


class CostingSheetLineItem(models.Model):
    class ProviderChoice(models.IntegerChoices):
        PROVIDER_1 = 1, "Provider 1"
        PROVIDER_2 = 2, "Provider 2"
        PROVIDER_3 = 3, "Provider 3"

    costing_sheet = models.ForeignKey(
        CostingSheet, on_delete=models.CASCADE, related_name="line_items"
    )
    line_item_id  = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    description   = models.CharField(max_length=500)
    unit          = models.CharField(max_length=100, blank=True)
    quantity      = models.PositiveIntegerField(default=1)

    # Provider quotes
    provider_1_name     = models.CharField(max_length=255, blank=True)
    provider_1_amount   = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    provider_1_currency = models.CharField(max_length=3, blank=True)

    provider_2_name     = models.CharField(max_length=255, blank=True)
    provider_2_amount   = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    provider_2_currency = models.CharField(max_length=3, blank=True)

    provider_3_name     = models.CharField(max_length=255, blank=True)
    provider_3_amount   = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    provider_3_currency = models.CharField(max_length=3, blank=True)

    selected_provider = models.IntegerField(choices=ProviderChoice.choices, null=True, blank=True)

    # Snapshotted at CDR_Approved — never overwritten after that
    original_approved_amount   = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    original_approved_currency = models.CharField(max_length=3, blank=True)

    # Set during Negotiating phase
    negotiated_amount   = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    negotiated_currency = models.CharField(max_length=3, blank=True)

    saved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="saved_line_items"
    )
    saved_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["saved_at"]

    def __str__(self):
        return f"{self.description} (qty {self.quantity})"

    @property
    def selected_amount(self):
        if self.negotiated_amount is not None:
            return self.negotiated_amount
        if self.original_approved_amount is not None:
            return self.original_approved_amount
        if self.selected_provider:
            return getattr(self, f"provider_{self.selected_provider}_amount", None)
        return None

    @property
    def selected_currency(self):
        if self.negotiated_currency:
            return self.negotiated_currency
        if self.original_approved_currency:
            return self.original_approved_currency
        if self.selected_provider:
            return getattr(self, f"provider_{self.selected_provider}_currency", "")
        return ""


class POYearCounter(models.Model):
    year    = models.IntegerField()
    prefix  = models.CharField(max_length=10, default="PO")
    counter = models.IntegerField(default=0)

    class Meta:
        unique_together = [("year", "prefix")]

    def __str__(self):
        return f"{self.prefix}-{self.year}: {self.counter}"


class PurchaseOrder(models.Model):
    class Status(models.TextChoices):
        DRAFT     = "Draft", "Draft"
        ISSUED    = "Issued", "Issued"
        FULFILLED = "Fulfilled", "Fulfilled"
        CANCELLED = "Cancelled", "Cancelled"

    costing_sheet       = models.ForeignKey(
        CostingSheet, on_delete=models.PROTECT, related_name="purchase_orders"
    )
    po_number           = models.CharField(max_length=20, unique=True)
    status              = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    pdr                 = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="purchase_orders_as_pdr"
    )
    issued_at           = models.DateTimeField(null=True, blank=True)
    fulfilled_at        = models.DateTimeField(null=True, blank=True)
    cancelled_at        = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def total_amount(self):
        total = Decimal('0')
        for line_item in self.line_items.select_related('costing_sheet_line_item').all():
            costing_item = line_item.costing_sheet_line_item
            amount = costing_item.selected_amount
            if amount is not None:
                quantity = costing_item.quantity or 1
                total += amount * quantity
        return total

    def __str__(self):
        return f"{self.po_number} [{self.status}]"


class POLineItem(models.Model):
    purchase_order          = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name="line_items"
    )
    costing_sheet_line_item = models.ForeignKey(
        CostingSheetLineItem, on_delete=models.PROTECT, related_name="po_line_items"
    )
    expected_delivery_date  = models.DateField()
    supplier_eta            = models.DateField(null=True, blank=True)
    actual_delivery_date    = models.DateField(null=True, blank=True)
    notify_client_required  = models.BooleanField(default=False)
    client_notified_at      = models.DateTimeField(null=True, blank=True)
    client_notified_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="client_notifications", null=True, blank=True
    )

    class Meta:
        ordering = ["expected_delivery_date"]

    @property
    def is_delayed(self):
        if self.supplier_eta and self.expected_delivery_date:
            return self.supplier_eta > self.expected_delivery_date
        return False


class ProcurementAuditEvent(models.Model):
    class Action(models.TextChoices):
        CS_CREATED             = "CS_CREATED", "CS Created"
        CS_SUBMITTED           = "CS_SUBMITTED", "CS Submitted"
        CS_CDR_APPROVED        = "CS_CDR_APPROVED", "CDR Approved"
        CS_CDR_REJECTED        = "CS_CDR_REJECTED", "CDR Rejected"
        CS_NEGOTIATION_STARTED = "CS_NEGOTIATION_STARTED", "Negotiation Started"
        CS_QUOTE_REVISED       = "CS_QUOTE_REVISED", "Quote Revised"
        CS_SUBMITTED_DIRECTOR  = "CS_SUBMITTED_DIRECTOR", "Submitted to Director"
        CS_DIRECTOR_APPROVED   = "CS_DIRECTOR_APPROVED", "Director Approved"
        CS_DIRECTOR_REJECTED   = "CS_DIRECTOR_REJECTED", "Director Rejected"
        CS_REMEDIATED          = "CS_REMEDIATED", "CS Remediated"
        LI_CREATED             = "LI_CREATED", "Line Item Created"
        LI_UPDATED             = "LI_UPDATED", "Line Item Updated"
        LI_DELETED             = "LI_DELETED", "Line Item Deleted"
        PO_GENERATED           = "PO_GENERATED", "PO Generated"
        PO_ISSUED              = "PO_ISSUED", "PO Issued"
        PO_FULFILLED           = "PO_FULFILLED", "PO Fulfilled"
        PO_CANCELLED           = "PO_CANCELLED", "PO Cancelled"
        ETA_RECORDED           = "ETA_RECORDED", "ETA Recorded"
        ETA_UPDATED            = "ETA_UPDATED", "ETA Updated"
        DELIVERY_RECORDED      = "DELIVERY_RECORDED", "Delivery Recorded"
        CLIENT_NOTIFIED        = "CLIENT_NOTIFIED", "Client Notified"

    costing_sheet = models.ForeignKey(
        CostingSheet, on_delete=models.PROTECT, related_name="audit_events"
    )
    actor     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action    = models.CharField(max_length=50, choices=Action.choices)
    detail    = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.action} on {self.costing_sheet} at {self.timestamp}"


class Certification(models.Model):
    class CertificationType(models.TextChoices):
        BLS = "BLS", "BLS"
        ACLS = "ACLS", "ACLS"
        PALS = "PALS", "PALS"
        ITLS = "ITLS", "ITLS"

    contact = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="certifications",
    )
    certification_type = models.CharField(
        max_length=10,
        choices=CertificationType.choices,
    )
    issue_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True)
    reminder_sent = models.BooleanField(default=False)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["expiry_date"]

    def __str__(self):
        return f"{self.contact.get_full_name() or self.contact.username} - {self.certification_type}"

    @classmethod
    def renewal_years_for(cls, certification_type):
        if certification_type == cls.CertificationType.ITLS:
            return 3
        return 2

    @staticmethod
    def _calculate_expiry(issue_date, years):
        try:
            return issue_date.replace(year=issue_date.year + years)
        except ValueError:
            return issue_date.replace(month=2, day=28, year=issue_date.year + years)

    def save(self, *args, **kwargs):
        if self.issue_date and not self.expiry_date:
            self.expiry_date = self._calculate_expiry(
                self.issue_date,
                self.renewal_years_for(self.certification_type),
            )
        super().save(*args, **kwargs)

    @property
    def days_until_expiry(self):
        if not self.expiry_date:
            return None
        return (self.expiry_date - date.today()).days

    @property
    def is_expiring_soon(self):
        remaining = self.days_until_expiry
        return remaining is not None and remaining <= 90

# Phase 4 models imported here so Django discovers them
from .stock_models import StockMovement, DeliveryDocument, ProofOfDelivery  # noqa: F401, E402
