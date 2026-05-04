from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .exceptions import TransitionError
from .models import AuditEvent, ApproverProfile, TRFApproval, TRFRequest
from .notifications import NotificationService


class ApprovalService:

    @staticmethod
    def _get_effective_profile(user):
        """
        Returns the ApproverProfile that grants this user approval rights.

        - If the user has their own profile and is_available → return it.
        - If the user has a profile but is unavailable → return None (they can't act for themselves).
        - If the user is listed as delegate on an unavailable approver's profile → return that approver's profile.
        - Otherwise → None.
        """
        own_profile = getattr(user, "approver_profile", None)

        if own_profile is not None and own_profile.is_available:
            return own_profile

        # Check if this user is a delegate for an unavailable approver at the same level.
        # ApproverProfile.delegate is a FK to self (another ApproverProfile).
        # "delegating_to" is the reverse: profiles that have delegated TO this profile.
        delegating_profiles = ApproverProfile.objects.filter(
            delegate__user=user,
            is_available=False,
        )
        if delegating_profiles.exists():
            return delegating_profiles.first()

        return None

    @staticmethod
    @transaction.atomic
    def submit(trf, user):
        """Transition DRAFT → PENDING_L2."""
        if trf.submitted_by_id != user.pk:
            raise TransitionError("Only the TRF owner can submit.")

        if trf.status != TRFRequest.Status.DRAFT:
            raise TransitionError(
                f"Cannot submit a TRF with status '{trf.status}'. Expected DRAFT."
            )

        if not trf.milestones.exists():
            raise TransitionError("TRF must have at least one milestone before submission.")

        if not trf.expenses.exists():
            raise TransitionError("TRF must have at least one expense before submission.")

        # Guard: ensure at least one L2 approver is reachable (directly or via delegate).
        available_l2 = ApproverProfile.objects.filter(level=2, is_available=True).exists()
        has_l2_delegate = ApproverProfile.objects.filter(
            level=2, is_available=False
        ).exclude(delegate=None).exists()
        if not available_l2 and not has_l2_delegate:
            raise TransitionError(
                "No Level 2 approvers are currently available. Please contact your administrator."
            )

        from_status = trf.status
        trf.status = TRFRequest.Status.PENDING_L2
        trf.submitted_at = timezone.now()
        trf.save(update_fields=["status", "submitted_at", "updated_at"])

        AuditEvent.objects.create(
            trf=trf,
            actor=user,
            action="SUBMITTED",
            from_status=from_status,
            to_status=trf.status,
        )

        transaction.on_commit(lambda: NotificationService.notify_l2_approvers(trf))
        return trf

    @staticmethod
    @transaction.atomic
    def approve(trf, user):
        """Transition PENDING_L2 → PENDING_L3 or PENDING_L3 → APPROVED."""
        valid_statuses = {TRFRequest.Status.PENDING_L2, TRFRequest.Status.PENDING_L3}
        if trf.status not in valid_statuses:
            raise TransitionError(
                f"Cannot approve a TRF with status '{trf.status}'."
            )

        profile = ApprovalService._get_effective_profile(user)
        if profile is None:
            raise PermissionError("User does not have an active approver role.")

        required_level = 2 if trf.status == TRFRequest.Status.PENDING_L2 else 3
        if profile.level != required_level:
            raise PermissionError(
                f"A Level {required_level} approver is required; user is Level {profile.level}."
            )

        # L3 guard: cannot be the same person who approved at L2 on this TRF.
        if trf.status == TRFRequest.Status.PENDING_L3:
            l2_approver_ids = list(
                trf.approvals.filter(
                    level=TRFApproval.Level.L2,
                    action=TRFApproval.Action.APPROVED,
                ).values_list("actor_id", flat=True)
            )
            if user.pk in l2_approver_ids:
                raise PermissionError(
                    "The user who approved at Level 2 cannot also approve at Level 3 on the same TRF."
                )

        from_status = trf.status
        if trf.status == TRFRequest.Status.PENDING_L2:
            to_status = TRFRequest.Status.PENDING_L3
            approval_level = TRFApproval.Level.L2
            action_label = "APPROVED_L2"
        else:
            to_status = TRFRequest.Status.APPROVED
            approval_level = TRFApproval.Level.L3
            action_label = "APPROVED_L3"

        # Guard: when transitioning to PENDING_L3, ensure at least one L3 approver is reachable.
        if to_status == TRFRequest.Status.PENDING_L3:
            available_l3 = ApproverProfile.objects.filter(level=3, is_available=True).exists()
            has_l3_delegate = ApproverProfile.objects.filter(
                level=3, is_available=False
            ).exclude(delegate=None).exists()
            if not available_l3 and not has_l3_delegate:
                raise TransitionError(
                    "No Level 3 approvers are currently available. Please contact your administrator."
                )

        trf.status = to_status
        trf.save(update_fields=["status", "updated_at"])

        TRFApproval.objects.create(
            trf=trf,
            level=approval_level,
            action=TRFApproval.Action.APPROVED,
            actor=user,
        )

        AuditEvent.objects.create(
            trf=trf,
            actor=user,
            action=action_label,
            from_status=from_status,
            to_status=to_status,
        )

        if to_status == TRFRequest.Status.PENDING_L3:
            transaction.on_commit(lambda: NotificationService.notify_l3_approvers(trf))
        elif to_status == TRFRequest.Status.APPROVED:
            transaction.on_commit(lambda: NotificationService.notify_post_approval(trf))

        return trf

    @staticmethod
    @transaction.atomic
    def reject(trf, user, reason):
        """Transition PENDING_L2 or PENDING_L3 → REJECTED."""
        valid_statuses = {TRFRequest.Status.PENDING_L2, TRFRequest.Status.PENDING_L3}
        if trf.status not in valid_statuses:
            raise TransitionError(
                f"Cannot reject a TRF with status '{trf.status}'."
            )

        if not reason or not reason.strip():
            raise ValueError("A rejection reason is required.")

        profile = ApprovalService._get_effective_profile(user)
        if profile is None:
            raise PermissionError("User does not have an active approver role.")

        required_level = 2 if trf.status == TRFRequest.Status.PENDING_L2 else 3
        if profile.level != required_level:
            raise PermissionError(
                f"A Level {required_level} approver is required; user is Level {profile.level}."
            )

        approval_level = TRFApproval.Level.L2 if required_level == 2 else TRFApproval.Level.L3
        action_label = f"REJECTED_L{required_level}"
        from_status = trf.status

        trf.status = TRFRequest.Status.REJECTED
        trf.save(update_fields=["status", "updated_at"])

        TRFApproval.objects.create(
            trf=trf,
            level=approval_level,
            action=TRFApproval.Action.REJECTED,
            actor=user,
            reason=reason.strip(),
        )

        AuditEvent.objects.create(
            trf=trf,
            actor=user,
            action=action_label,
            from_status=from_status,
            to_status=trf.status,
            reason=reason.strip(),
        )

        _reason = reason.strip()
        transaction.on_commit(lambda: NotificationService.notify_submitter_rejected(trf, _reason))
        return trf

    @staticmethod
    @transaction.atomic
    def remediate(trf, user, cleaned_data):
        """Transition REJECTED → PENDING_L2 after editing at least one field."""
        if trf.submitted_by_id != user.pk:
            raise TransitionError("Only the TRF owner can remediate.")

        if trf.status != TRFRequest.Status.REJECTED:
            raise TransitionError(
                f"Cannot remediate a TRF with status '{trf.status}'. Expected REJECTED."
            )

        # Determine which fields we manage in remediation.
        managed_fields = ["project_name", "training_start"]

        # Build a snapshot of current values for comparison.
        current_values = {f: getattr(trf, f) for f in managed_fields}

        # Normalise cleaned_data values for comparison (dates may come as strings).
        def _normalise(val):
            if hasattr(val, "isoformat"):
                return str(val)
            return val

        snapshot = trf.previous_snapshot or {}
        has_change = False
        for field in managed_fields:
            new_val = cleaned_data.get(field)
            if new_val is None:
                continue
            if _normalise(new_val) != _normalise(current_values[field]):
                has_change = True
                break

        # Also check against previous_snapshot if present.
        if not has_change and snapshot:
            for field in managed_fields:
                new_val = cleaned_data.get(field)
                if new_val is None:
                    continue
                if _normalise(new_val) != _normalise(snapshot.get(field)):
                    has_change = True
                    break

        if not has_change:
            raise ValidationError(
                "At least one field must be changed before resubmitting."
            )

        # Snapshot current values before applying changes.
        trf.previous_snapshot = {f: _normalise(current_values[f]) for f in managed_fields}

        # Apply changes.
        for field in managed_fields:
            if field in cleaned_data:
                setattr(trf, field, cleaned_data[field])

        from_status = trf.status
        trf.status = TRFRequest.Status.PENDING_L2
        trf.remediated_at = timezone.now()
        trf.save(update_fields=["status", "remediated_at", "previous_snapshot", "updated_at"] + managed_fields)

        AuditEvent.objects.create(
            trf=trf,
            actor=user,
            action="REMEDIATED",
            from_status=from_status,
            to_status=trf.status,
        )

        return trf
