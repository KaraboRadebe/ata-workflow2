import uuid
from django.conf import settings
from django.db import models


class TRFRequest(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING_L2 = "PENDING_L2", "Pending L2"
        PENDING_L3 = "PENDING_L3", "Pending L3"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        REMEDIATION = "REMEDIATION", "Remediation"

    project_name = models.CharField(max_length=255)
    training_start = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="trf_submissions",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    remediated_at = models.DateTimeField(null=True, blank=True)
    previous_snapshot = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.project_name} [{self.status}]"


class Milestone(models.Model):
    trf = models.ForeignKey(TRFRequest, on_delete=models.CASCADE, related_name="milestones")
    name = models.CharField(max_length=255)
    target_date = models.DateField()

    def __str__(self):
        return f"{self.name} ({self.target_date})"


class Expense(models.Model):
    trf = models.ForeignKey(TRFRequest, on_delete=models.CASCADE, related_name="expenses")
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)  # ISO 4217
    line_item_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    def __str__(self):
        return f"{self.description} {self.amount} {self.currency}"


class TRFApproval(models.Model):
    class Level(models.IntegerChoices):
        L2 = 2, "Level 2"
        L3 = 3, "Level 3"

    class Action(models.TextChoices):
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    trf = models.ForeignKey(TRFRequest, on_delete=models.PROTECT, related_name="approvals")
    level = models.IntegerField(choices=Level.choices)
    action = models.CharField(max_length=10, choices=Action.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.TextField(blank=True)
    acted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"L{self.level} {self.action} by {self.actor} on {self.trf}"


class AuditEvent(models.Model):
    trf = models.ForeignKey(TRFRequest, on_delete=models.PROTECT, related_name="audit_events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=50)
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    reason = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.action}: {self.from_status} → {self.to_status} ({self.timestamp})"


class ApproverProfile(models.Model):
    class Level(models.IntegerChoices):
        L2 = 2, "Level 2"
        L3 = 3, "Level 3"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="approver_profile",
    )
    level = models.IntegerField(choices=Level.choices)
    is_available = models.BooleanField(default=True)
    delegate = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="delegating_to",
    )

    def __str__(self):
        return f"{self.user.username} (L{self.level}, {'available' if self.is_available else 'unavailable'})"


class NotificationLog(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "EMAIL", "Email"
        SLACK = "SLACK", "Slack"
        IN_APP = "IN_APP", "In-App"

    class Result(models.TextChoices):
        SUCCESS = "SUCCESS", "Success"
        FAILURE = "FAILURE", "Failure"

    trf = models.ForeignKey(TRFRequest, on_delete=models.PROTECT, related_name="notification_logs")
    channel = models.CharField(max_length=10, choices=Channel.choices)
    recipient = models.CharField(max_length=255)
    result = models.CharField(max_length=10, choices=Result.choices)
    error_msg = models.TextField(blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.channel} → {self.recipient} [{self.result}]"
