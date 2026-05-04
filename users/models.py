from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    # Their actual job title from SharePoint
    job_title = models.CharField(max_length=100, blank=True, help_text="SharePoint job title")
    
    # Approval level (only for approvers)
    class ApprovalLevel(models.TextChoices):
        NONE = "None", "Not an Approver"
        L2 = "L2", "Level 2 Approver"
        L3 = "L3", "Level 3 Approver"
    
    approval_level = models.CharField(
        max_length=10,
        choices=ApprovalLevel.choices,
        default=ApprovalLevel.NONE,
        help_text="Approval level for TRF workflow"
    )
    
    # System role (what they can access)
    class SystemRole(models.TextChoices):
        SALES = "Sales", "Sales User"
        PC = "PC", "Project Coordinator"
        PDR = "PDR", "Procurement"
        CDR = "CDR", "Costing"
        OPS = "Ops", "Operations"
        FINANCE = "Finance", "Finance"
        DIRECTOR = "Director", "Director"
        ADMIN = "Admin", "Admin"

    system_role = models.CharField(
        max_length=20,
        choices=SystemRole.choices,
        default=SystemRole.SALES,
    )

    def __str__(self):
        return f"{self.get_full_name() or self.username} - {self.job_title or self.system_role}"

    @property
    def has_approver_profile(self):
        return self.approval_level != self.ApprovalLevel.NONE