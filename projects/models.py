from django.conf import settings
from django.db import models


class Project(models.Model):
    class Status(models.TextChoices):
        ACTIVE    = "Active", "Active"
        ON_HOLD   = "On_Hold", "On Hold"
        COMPLETED = "Completed", "Completed"
        CANCELLED = "Cancelled", "Cancelled"

    trf = models.OneToOneField(
        "trf.TRFRequest", on_delete=models.PROTECT, related_name="project"
    )
    name = models.CharField(max_length=255)
    sales_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_projects"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    trf_approved_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} [{self.status}]"


class Milestone(models.Model):
    class Status(models.TextChoices):
        PENDING     = "Pending", "Pending"
        IN_PROGRESS = "In_Progress", "In Progress"
        COMPLETED   = "Completed", "Completed"
        CANCELLED   = "Cancelled", "Cancelled"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="milestones")
    name = models.CharField(max_length=255)
    target_date = models.DateField()
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # TRF Expense linkage
    is_trf_expense = models.BooleanField(default=False)
    cost_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True)

    # Read-only snapshot fields (set once on creation, never updated)
    costing_sheet_line_item_id = models.CharField(max_length=100, blank=True)
    original_cost_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    original_currency = models.CharField(max_length=3, blank=True)

    # Tracking
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_milestones"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="updated_milestones",
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["target_date"]

    def __str__(self):
        return f"{self.name} ({self.target_date})"

    @property
    def has_cost_variance(self) -> bool:
        if not self.is_trf_expense or self.original_cost_amount is None:
            return False
        return self.cost_amount != self.original_cost_amount or self.currency != self.original_currency


class ProjectAuditEvent(models.Model):
    class Action(models.TextChoices):
        PROJECT_CREATED   = "PROJECT_CREATED", "Project Created"
        STATUS_CHANGED    = "STATUS_CHANGED", "Status Changed"
        MILESTONE_CREATED = "MILESTONE_CREATED", "Milestone Created"
        MILESTONE_UPDATED = "MILESTONE_UPDATED", "Milestone Updated"
        MILESTONE_DELETED = "MILESTONE_DELETED", "Milestone Deleted"

    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="audit_events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=50, choices=Action.choices)
    detail = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.action} on {self.project} at {self.timestamp}"
