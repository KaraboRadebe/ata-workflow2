from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum

User = settings.AUTH_USER_MODEL


class PaymentRequisition(models.Model):
    class RequisitionType(models.TextChoices):
        INTERNAL = 'INTERNAL', 'Internal Expense'
        CLIENT = 'CLIENT', 'Client Billable'
        SUPPLIER = 'SUPPLIER', 'Supplier Payment'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        SUBMITTED = 'SUBMITTED', 'Submitted'
        L2_APPROVED = 'L2_APPROVED', 'Level 2 Approved'
        L3_APPROVED = 'L3_APPROVED', 'Level 3 Approved'
        REJECTED = 'REJECTED', 'Rejected'
        PAID = 'PAID', 'Paid'
        CLOSED = 'CLOSED', 'Closed'

    # Basic fields
    requisition_type = models.CharField(max_length=20, choices=RequisitionType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, default='ZAR')
    description = models.TextField()
    
    # Linked objects (one of these)
    trf = models.ForeignKey('trf.TRFRequest', null=True, blank=True, on_delete=models.PROTECT)
    project = models.ForeignKey('projects.Project', null=True, blank=True, on_delete=models.PROTECT)
    purchase_order = models.ForeignKey('procurement.PurchaseOrder', null=True, blank=True, on_delete=models.PROTECT)
    
    # Requestor info
    requested_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='payment_requests')
    requested_date = models.DateTimeField(auto_now_add=True)
    
    # Approval info
    approved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='payment_approvals')
    approved_date = models.DateTimeField(null=True, blank=True)
    
    # Payment info
    payment_date = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    proof_of_payment = models.FileField(upload_to='payments/%Y/%m/%d/', null=True, blank=True)
    
    # Rejection info
    rejection_reason = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_requisition_type_display()} - {self.amount} {self.currency}"

    @property
    def total_budget(self):
        """Calculate total budget from linked object."""
        if self.trf:
            total = self.trf.expenses.aggregate(total=Sum('amount'))['total']
            return total or Decimal('0')

        if self.project:
            return sum((m.cost_amount or Decimal('0')) for m in self.project.milestones.all())

        if self.purchase_order:
            return self.purchase_order.total_amount

        return Decimal('0')

    @property
    def budget_used(self):
        if self.trf:
            qs = PaymentRequisition.objects.filter(trf=self.trf)
        elif self.project:
            qs = PaymentRequisition.objects.filter(project=self.project)
        elif self.purchase_order:
            qs = PaymentRequisition.objects.filter(purchase_order=self.purchase_order)
        else:
            return Decimal('0')

        used = qs.exclude(pk=self.pk).exclude(status=self.Status.REJECTED).aggregate(total=Sum('amount'))['total']
        return used or Decimal('0')

    @property
    def budget_remaining(self):
        return self.total_budget - self.budget_used

    @property
    def budget_remaining_after(self):
        return self.budget_remaining - self.amount


class PaymentRequisitionApproval(models.Model):
    payment_requisition = models.ForeignKey(PaymentRequisition, on_delete=models.CASCADE, related_name='approvals')
    approver = models.ForeignKey(User, on_delete=models.PROTECT)
    level = models.IntegerField(choices=[(2, 'Level 2'), (3, 'Level 3')])
    status = models.CharField(max_length=20, choices=[('PENDING', 'Pending'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected')])
    comment = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = [['payment_requisition', 'approver', 'level']]


class PaymentAuditEvent(models.Model):
    payment_requisition = models.ForeignKey(PaymentRequisition, on_delete=models.PROTECT, related_name='audit_events')
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    action = models.CharField(max_length=50)
    detail = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)