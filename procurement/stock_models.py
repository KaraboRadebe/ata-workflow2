"""
Phase 4: Stock receiving, delivery documents, and POD (Proof of Delivery).
These models extend the procurement app.
"""
import os
from django.conf import settings
from django.db import models
from .models import PurchaseOrder, POLineItem


def delivery_doc_upload_path(instance, filename):
    return f"delivery_docs/po_{instance.purchase_order.pk}/{filename}"


def pod_upload_path(instance, filename):
    return f"pod/po_{instance.purchase_order.pk}/{filename}"


class StockMovement(models.Model):
    """Tracks the physical journey of stock for a PO line item."""

    class Stage(models.TextChoices):
        ORDERED   = "Ordered",   "Ordered"
        RECEIVED  = "Received",  "Received"
        VETTED    = "Vetted",    "Vetted"
        PACKED    = "Packed",    "Packed"
        DELIVERED = "Delivered", "Delivered"

    po_line_item = models.OneToOneField(
        POLineItem, on_delete=models.CASCADE, related_name="stock_movement"
    )
    stage        = models.CharField(max_length=20, choices=Stage.choices, default=Stage.ORDERED)
    notes        = models.TextField(blank=True)
    updated_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="stock_movements_updated", null=True, blank=True
    )
    updated_at   = models.DateTimeField(auto_now=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.po_line_item} — {self.stage}"


class DeliveryDocument(models.Model):
    """Photos, COAS, compliance docs uploaded before delivery."""

    class DocType(models.TextChoices):
        PHOTO      = "Photo",      "Stock Photo"
        COAS       = "COAS",       "Certificate of Analysis (COAS)"
        COMPLIANCE = "Compliance", "Compliance Document"
        OTHER      = "Other",      "Other"

    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name="delivery_documents"
    )
    doc_type       = models.CharField(max_length=20, choices=DocType.choices)
    file           = models.FileField(upload_to=delivery_doc_upload_path)
    description    = models.CharField(max_length=255, blank=True)
    uploaded_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="uploaded_delivery_docs"
    )
    uploaded_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.doc_type} for PO {self.purchase_order.po_number}"

    @property
    def filename(self):
        return os.path.basename(self.file.name)


class ProofOfDelivery(models.Model):
    """Signed POD uploaded by PDR after delivery."""

    purchase_order    = models.OneToOneField(
        PurchaseOrder, on_delete=models.CASCADE, related_name="pod"
    )
    pod_file          = models.FileField(upload_to=pod_upload_path)
    signed_by         = models.CharField(max_length=255, help_text="Name of person who signed")
    signed_at         = models.DateField()
    notes             = models.TextField(blank=True)
    uploaded_by       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="uploaded_pods"
    )
    uploaded_at       = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"POD for {self.purchase_order.po_number} — signed by {self.signed_by}"
