import logging

from django.db import IntegrityError, transaction

from .exceptions import MilestoneDeletionError, ProjectTransitionError
from .models import Milestone, Project, ProjectAuditEvent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Allowed status transitions
# ---------------------------------------------------------------------------
ALLOWED_TRANSITIONS = {
    Project.Status.ACTIVE: {
        Project.Status.ON_HOLD,
        Project.Status.COMPLETED,
        Project.Status.CANCELLED,
    },
    Project.Status.ON_HOLD: {
        Project.Status.ACTIVE,
    },
}

INCOMPLETE_STATUSES = {Milestone.Status.PENDING, Milestone.Status.IN_PROGRESS}


# ---------------------------------------------------------------------------
# ProjectAuditService
# ---------------------------------------------------------------------------
class ProjectAuditService:
    @staticmethod
    def record(project, actor, action, detail=None):
        """INSERT-only — never updates an existing audit event."""
        return ProjectAuditEvent.objects.create(
            project=project,
            actor=actor,
            action=action,
            detail=detail or {},
        )


# ---------------------------------------------------------------------------
# ProjectService
# ---------------------------------------------------------------------------
class ProjectService:
    @staticmethod
    def create_from_trf(trf):
        """
        Called by the post_save signal when a TRF reaches APPROVED status.
        Wrapped in transaction.atomic(). Failures are caught and logged;
        the TRF status is never rolled back.
        """
        try:
            with transaction.atomic():
                project = Project.objects.create(
                    trf=trf,
                    name=trf.project_name,
                    sales_user=trf.submitted_by,
                    trf_approved_at=trf.updated_at,
                )

                for expense in trf.expenses.all():
                    Milestone.objects.create(
                        project=project,
                        name=expense.description,
                        target_date=trf.training_start,
                        is_trf_expense=True,
                        cost_amount=expense.amount,
                        currency=expense.currency,
                        costing_sheet_line_item_id=str(expense.line_item_id),
                        original_cost_amount=expense.amount,
                        original_currency=expense.currency,
                        created_by=trf.submitted_by,
                    )

                ProjectAuditService.record(
                    project,
                    trf.submitted_by,
                    ProjectAuditEvent.Action.PROJECT_CREATED,
                )

                return project

        except IntegrityError:
            logger.exception(
                "Duplicate project creation blocked for TRF id=%s at %s",
                trf.pk,
                trf.updated_at,
            )
        except Exception:
            logger.exception(
                "Failed to create project for TRF id=%s at %s",
                trf.pk,
                trf.updated_at,
            )

    @staticmethod
    def transition_status(project, user, new_status, reason="", confirmed=False):
        """
        Validates the transition against the allowed table and writes an audit event.

        For Active → Completed with incomplete milestones and confirmed=False,
        returns a warning dict instead of transitioning.
        """
        current = project.status
        allowed = ALLOWED_TRANSITIONS.get(current, set())

        if new_status not in allowed:
            raise ProjectTransitionError(
                f"Cannot transition project from '{current}' to '{new_status}'."
            )

        # Completion guard: warn about incomplete milestones
        if (
            current == Project.Status.ACTIVE
            and new_status == Project.Status.COMPLETED
            and not confirmed
        ):
            incomplete = list(
                project.milestones.filter(status__in=INCOMPLETE_STATUSES)
            )
            if incomplete:
                return {"warning": True, "incomplete_milestones": incomplete}

        project.status = new_status
        project.save(update_fields=["status", "updated_at"])

        ProjectAuditService.record(
            project,
            user,
            ProjectAuditEvent.Action.STATUS_CHANGED,
            {"from_status": current, "to_status": new_status, "reason": reason},
        )

        return project


# ---------------------------------------------------------------------------
# MilestoneService
# ---------------------------------------------------------------------------
class MilestoneService:
    @staticmethod
    def _validate_create_update(project, data, is_trf_expense):
        if project.status != Project.Status.ACTIVE:
            raise ValueError("Milestones can only be added or edited on Active projects.")
        if not data.get("name"):
            raise ValueError("Milestone name is required.")
        if not data.get("target_date"):
            raise ValueError("Milestone target date is required.")
        if is_trf_expense:
            if not data.get("cost_amount"):
                raise ValueError("cost_amount is required for TRF expense milestones.")
            if not data.get("currency"):
                raise ValueError("currency is required for TRF expense milestones.")

    @staticmethod
    def create(project, user, data):
        is_trf_expense = data.get("is_trf_expense", False)
        MilestoneService._validate_create_update(project, data, is_trf_expense)

        milestone = Milestone.objects.create(
            project=project,
            name=data["name"],
            target_date=data["target_date"],
            description=data.get("description", ""),
            status=Milestone.Status.PENDING,
            is_trf_expense=is_trf_expense,
            cost_amount=data.get("cost_amount"),
            currency=data.get("currency", ""),
            created_by=user,
        )

        ProjectAuditService.record(
            project,
            user,
            ProjectAuditEvent.Action.MILESTONE_CREATED,
            {"milestone_name": milestone.name, "milestone_id": milestone.pk},
        )

        return milestone

    @staticmethod
    def update(milestone, user, data):
        project = milestone.project
        is_trf_expense = data.get("is_trf_expense", milestone.is_trf_expense)
        MilestoneService._validate_create_update(project, data, is_trf_expense)

        editable_fields = [
            "name", "target_date", "description", "status",
            "is_trf_expense", "cost_amount", "currency",
        ]
        for field in editable_fields:
            if field in data:
                setattr(milestone, field, data[field])

        # If is_trf_expense flipped to False, clear cost fields
        if not milestone.is_trf_expense:
            milestone.cost_amount = None
            milestone.currency = ""

        # Never touch original_* fields
        milestone.updated_by = user
        milestone.save(update_fields=[
            "name", "target_date", "description", "status",
            "is_trf_expense", "cost_amount", "currency",
            "updated_by", "updated_at",
        ])

        ProjectAuditService.record(
            project,
            user,
            ProjectAuditEvent.Action.MILESTONE_UPDATED,
            {"milestone_name": milestone.name, "milestone_id": milestone.pk},
        )

        return milestone

    @staticmethod
    def delete(milestone, user):
        if milestone.status == Milestone.Status.IN_PROGRESS:
            raise MilestoneDeletionError(
                "This milestone is In Progress. Change its status to Pending before deleting."
            )
        if milestone.status == Milestone.Status.COMPLETED:
            raise MilestoneDeletionError("Completed milestones cannot be deleted.")

        # Pending and Cancelled are deletable
        ProjectAuditService.record(
            milestone.project,
            user,
            ProjectAuditEvent.Action.MILESTONE_DELETED,
            {"milestone_name": milestone.name, "milestone_id": milestone.pk},
        )
        milestone.delete()
