import json
import logging
import urllib.request
from urllib.error import URLError

from django.conf import settings
from django.core.mail import send_mail

from .models import ApproverProfile, NotificationLog

logger = logging.getLogger(__name__)


class NotificationService:

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _log(trf, channel, recipient, result, error_msg=""):
        NotificationLog.objects.create(
            trf=trf,
            channel=channel,
            recipient=recipient,
            result=result,
            error_msg=error_msg,
        )

    @staticmethod
    def _recipient_for(user):
        """Return email if set, otherwise fall back to username."""
        return user.email or user.username

    # ------------------------------------------------------------------ #
    #  7.1 — Approver / submitter notifications                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def notify_l2_approvers(trf):
        """In-app + email notification to all available L2 approvers."""
        approvers = ApproverProfile.objects.filter(
            level=ApproverProfile.Level.L2,
            is_available=True,
        ).select_related("user")

        for profile in approvers:
            user = profile.user
            recipient = NotificationService._recipient_for(user)

            # In-app log (always SUCCESS — it's just a DB record)
            NotificationService._log(
                trf,
                NotificationLog.Channel.IN_APP,
                recipient,
                NotificationLog.Result.SUCCESS,
            )

            # Email
            subject = f"[ATA] TRF Pending Your Approval: {trf.project_name}"
            body = (
                f"A Training Request Form requires your approval.\n\n"
                f"Project: {trf.project_name}\n"
                f"Training Start: {trf.training_start}\n"
                f"Submitted By: {trf.submitted_by.get_full_name() or trf.submitted_by.username}\n\n"
                f"Please log in to the ATA Workflow Manager to review and approve or reject this TRF."
            )
            try:
                send_mail(
                    subject,
                    body,
                    settings.DEFAULT_FROM_EMAIL,
                    [recipient],
                    fail_silently=False,
                )
                NotificationService._log(
                    trf,
                    NotificationLog.Channel.EMAIL,
                    recipient,
                    NotificationLog.Result.SUCCESS,
                )
            except Exception as exc:
                logger.exception("Failed to email L2 approver %s for TRF %s", recipient, trf.pk)
                NotificationService._log(
                    trf,
                    NotificationLog.Channel.EMAIL,
                    recipient,
                    NotificationLog.Result.FAILURE,
                    error_msg=str(exc),
                )

    @staticmethod
    def notify_l3_approvers(trf):
        """In-app + email notification to all available L3 approvers."""
        approvers = ApproverProfile.objects.filter(
            level=ApproverProfile.Level.L3,
            is_available=True,
        ).select_related("user")

        for profile in approvers:
            user = profile.user
            recipient = NotificationService._recipient_for(user)

            # In-app log
            NotificationService._log(
                trf,
                NotificationLog.Channel.IN_APP,
                recipient,
                NotificationLog.Result.SUCCESS,
            )

            # Email
            subject = f"[ATA] TRF Ready for Final Approval: {trf.project_name}"
            body = (
                f"A Training Request Form has passed Level 2 review and requires your final approval.\n\n"
                f"Project: {trf.project_name}\n"
                f"Training Start: {trf.training_start}\n"
                f"Submitted By: {trf.submitted_by.get_full_name() or trf.submitted_by.username}\n\n"
                f"Please log in to the ATA Workflow Manager to review and approve or reject this TRF."
            )
            try:
                send_mail(
                    subject,
                    body,
                    settings.DEFAULT_FROM_EMAIL,
                    [recipient],
                    fail_silently=False,
                )
                NotificationService._log(
                    trf,
                    NotificationLog.Channel.EMAIL,
                    recipient,
                    NotificationLog.Result.SUCCESS,
                )
            except Exception as exc:
                logger.exception("Failed to email L3 approver %s for TRF %s", recipient, trf.pk)
                NotificationService._log(
                    trf,
                    NotificationLog.Channel.EMAIL,
                    recipient,
                    NotificationLog.Result.FAILURE,
                    error_msg=str(exc),
                )

    @staticmethod
    def notify_submitter_rejected(trf, reason):
        """In-app + email notification to the TRF submitter on rejection."""
        user = trf.submitted_by
        recipient = NotificationService._recipient_for(user)

        # In-app log
        NotificationService._log(
            trf,
            NotificationLog.Channel.IN_APP,
            recipient,
            NotificationLog.Result.SUCCESS,
        )

        # Email
        subject = f"[ATA] TRF Rejected: {trf.project_name}"
        body = (
            f"Your Training Request Form has been rejected.\n\n"
            f"Project: {trf.project_name}\n"
            f"Rejection Reason: {reason}\n\n"
            f"To remediate, please log in to the ATA Workflow Manager, open the TRF, "
            f"update the relevant fields, and resubmit. At least one field must be changed "
            f"before resubmission is allowed."
        )
        try:
            send_mail(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                [recipient],
                fail_silently=False,
            )
            NotificationService._log(
                trf,
                NotificationLog.Channel.EMAIL,
                recipient,
                NotificationLog.Result.SUCCESS,
            )
        except Exception as exc:
            logger.exception("Failed to email submitter %s for rejected TRF %s", recipient, trf.pk)
            NotificationService._log(
                trf,
                NotificationLog.Channel.EMAIL,
                recipient,
                NotificationLog.Result.FAILURE,
                error_msg=str(exc),
            )

    # ------------------------------------------------------------------ #
    #  7.2 — Post-approval notifications                                  #
    # ------------------------------------------------------------------ #

    @staticmethod
    def notify_post_approval(trf):
        """Email Finance + email Ops + optional Slack after full approval."""
        milestones = trf.milestones.all()
        expenses = trf.expenses.all()
        total = sum(e.amount for e in expenses)

        # ---- Finance email ------------------------------------------- #
        milestone_lines = "\n".join(
            f"  - {m.name}: {m.target_date}" for m in milestones
        )
        expense_lines = "\n".join(
            f"  - {e.description}: {e.amount} {e.currency}" for e in expenses
        )
        finance_body = (
            f"A Training Request Form has been fully approved.\n\n"
            f"Project: {trf.project_name}\n"
            f"Training Start: {trf.training_start}\n\n"
            f"Milestones:\n{milestone_lines or '  (none)'}\n\n"
            f"Expenses:\n{expense_lines or '  (none)'}\n\n"
            f"Total Expenses: {total}\n"
        )
        try:
            send_mail(
                f"[ATA] TRF Fully Approved: {trf.project_name}",
                finance_body,
                settings.DEFAULT_FROM_EMAIL,
                [settings.FINANCE_EMAIL],
                fail_silently=False,
            )
            NotificationService._log(
                trf,
                NotificationLog.Channel.EMAIL,
                settings.FINANCE_EMAIL,
                NotificationLog.Result.SUCCESS,
            )
        except Exception as exc:
            logger.exception("Failed to email Finance for TRF %s", trf.pk)
            NotificationService._log(
                trf,
                NotificationLog.Channel.EMAIL,
                settings.FINANCE_EMAIL,
                NotificationLog.Result.FAILURE,
                error_msg=str(exc),
            )

        # ---- Operations email ---------------------------------------- #
        ops_body = (
            f"A Training Request Form has been approved and requires your action.\n\n"
            f"Project: {trf.project_name}\n"
            f"Training Start: {trf.training_start}\n\n"
            f"Milestones:\n{milestone_lines or '  (none)'}\n"
        )
        try:
            send_mail(
                f"[ATA] Training Approved - Action Required: {trf.project_name}",
                ops_body,
                settings.DEFAULT_FROM_EMAIL,
                [settings.OPS_EMAIL],
                fail_silently=False,
            )
            NotificationService._log(
                trf,
                NotificationLog.Channel.EMAIL,
                settings.OPS_EMAIL,
                NotificationLog.Result.SUCCESS,
            )
        except Exception as exc:
            logger.exception("Failed to email Ops for TRF %s", trf.pk)
            NotificationService._log(
                trf,
                NotificationLog.Channel.EMAIL,
                settings.OPS_EMAIL,
                NotificationLog.Result.FAILURE,
                error_msg=str(exc),
            )

        # ---- Slack webhook (optional) --------------------------------- #
        webhook_url = getattr(settings, "SLACK_OPS_WEBHOOK_URL", "")
        if not webhook_url:
            return

        payload = json.dumps(
            {"text": f"✅ TRF Approved: *{trf.project_name}* — Training starts {trf.training_start}"}
        ).encode("utf-8")

        try:
            req = urllib.request.Request(
                webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                status_code = response.status

            if status_code == 200:
                NotificationService._log(
                    trf,
                    NotificationLog.Channel.SLACK,
                    webhook_url,
                    NotificationLog.Result.SUCCESS,
                )
            else:
                NotificationService._log(
                    trf,
                    NotificationLog.Channel.SLACK,
                    webhook_url,
                    NotificationLog.Result.FAILURE,
                    error_msg=f"Unexpected HTTP status: {status_code}",
                )
        except Exception as exc:
            logger.exception("Failed to send Slack notification for TRF %s", trf.pk)
            NotificationService._log(
                trf,
                NotificationLog.Channel.SLACK,
                webhook_url,
                NotificationLog.Result.FAILURE,
                error_msg=str(exc),
            )
