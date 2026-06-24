import logging
from datetime import date, timedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone

from .payment_models import PaymentRequisition, PaymentRequisitionApproval, PaymentAuditEvent
from .models import Certification
from trf.models import ApproverProfile, TRFApproval
from projects.models import Project

logger = logging.getLogger(__name__)


class PaymentNotificationService:
    @staticmethod
    def _recipient_for(user):
        return user.email or user.username

    @staticmethod
    def _send_email(subject, body, recipients):
        try:
            send_mail(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                recipients,
                fail_silently=False,
            )
        except Exception:
            logger.exception("Failed to send payment notification to %s", recipients)

    @staticmethod
    def notify_l2_approvers(requisition):
        approvers = ApproverProfile.objects.filter(level=2, is_available=True).select_related('user')
        recipients = [PaymentNotificationService._recipient_for(profile.user) for profile in approvers]
        if not recipients:
            logger.warning("No available L2 approvers for payment requisition %s", requisition.pk)
            return
        subject = f"[ATA] Payment Requisition Awaiting Level 2 Approval"
        body = (
            f"A payment requisition has been submitted and requires Level 2 approval.\n\n"
            f"Requisition: {requisition}\n"
            f"Amount: {requisition.amount} {requisition.currency}\n"
            f"Requested By: {requisition.requested_by.get_full_name() or requisition.requested_by.username}\n"
            f"Please sign in to review and approve the request."
        )
        PaymentNotificationService._send_email(subject, body, recipients)

    @staticmethod
    def notify_l3_approvers(requisition):
        approvers = ApproverProfile.objects.filter(level=3, is_available=True).select_related('user')
        recipients = [PaymentNotificationService._recipient_for(profile.user) for profile in approvers]
        if not recipients:
            logger.warning("No available L3 approvers for payment requisition %s", requisition.pk)
            return
        subject = f"[ATA] Payment Requisition Awaiting Level 3 Approval"
        body = (
            f"A payment requisition has been approved at Level 2 and requires Level 3 approval.\n\n"
            f"Requisition: {requisition}\n"
            f"Amount: {requisition.amount} {requisition.currency}\n"
            f"Requested By: {requisition.requested_by.get_full_name() or requisition.requested_by.username}\n"
            f"Please sign in to review and approve the request."
        )
        PaymentNotificationService._send_email(subject, body, recipients)

    @staticmethod
    def notify_requester_paid(requisition):
        recipient = PaymentNotificationService._recipient_for(requisition.requested_by)
        subject = f"[ATA] Payment Requisition Paid: {requisition}"
        body = (
            f"Your payment requisition has been marked as paid.\n\n"
            f"Requisition: {requisition}\n"
            f"Amount: {requisition.amount} {requisition.currency}\n"
            f"Payment Reference: {requisition.payment_reference}\n"
        )
        PaymentNotificationService._send_email(subject, body, [recipient])


class PaymentRequisitionService:

    @staticmethod
    def create(requisition_data, user):
        trf = requisition_data.get('trf')
        project = requisition_data.get('project')
        purchase_order = requisition_data.get('purchase_order')
        selected = [obj for obj in (trf, project, purchase_order) if obj is not None]
        if len(selected) != 1:
            raise ValidationError("Exactly one of TRF, Project, or Purchase Order must be selected.")

        with transaction.atomic():
            requisition = PaymentRequisition.objects.create(
                requisition_type=requisition_data['requisition_type'],
                amount=requisition_data['amount'],
                currency=requisition_data.get('currency', 'ZAR'),
                description=requisition_data['description'],
                trf=trf,
                project=project,
                purchase_order=purchase_order,
                requested_by=user,
            )
            PaymentAuditEvent.objects.create(
                payment_requisition=requisition,
                actor=user,
                action='CREATED',
                detail={'status': requisition.status},
            )
            return requisition

    @staticmethod
    def submit(requisition, user):
        if requisition.status != PaymentRequisition.Status.DRAFT:
            raise ValidationError("Only draft requisitions can be submitted.")

        if requisition.amount > requisition.budget_remaining:
            raise ValidationError(
                f"Amount exceeds remaining budget by {requisition.amount - requisition.budget_remaining}"
            )

        with transaction.atomic():
            requisition.status = PaymentRequisition.Status.SUBMITTED
            requisition.save(update_fields=['status', 'updated_at'])

            l2_approvers = ApproverProfile.objects.filter(level=2, is_available=True)
            if not l2_approvers.exists():
                raise ValidationError("No available Level 2 approvers are configured.")

            approvals = [
                PaymentRequisitionApproval(
                    payment_requisition=requisition,
                    approver=profile.user,
                    level=2,
                    status='PENDING',
                )
                for profile in l2_approvers
            ]
            PaymentRequisitionApproval.objects.bulk_create(approvals)

            PaymentAuditEvent.objects.create(
                payment_requisition=requisition,
                actor=user,
                action='SUBMITTED',
                detail={'status': requisition.status},
            )
            transaction.on_commit(lambda: PaymentNotificationService.notify_l2_approvers(requisition))
            return requisition

    @staticmethod
    def approve_l2(requisition, approver):
        if requisition.status != PaymentRequisition.Status.SUBMITTED:
            raise ValidationError("Requisition is not in submitted state.")

        approval = PaymentRequisitionApproval.objects.filter(
            payment_requisition=requisition,
            level=2,
            approver=approver,
            status='PENDING',
        ).first()
        if not approval:
            raise ValidationError("No pending Level 2 approval found for this user.")

        with transaction.atomic():
            approval.status = 'APPROVED'
            approval.approved_at = timezone.now()
            approval.save(update_fields=['status', 'approved_at'])

            requisition.status = PaymentRequisition.Status.L2_APPROVED
            requisition.save(update_fields=['status', 'updated_at'])

            l3_approvers = ApproverProfile.objects.filter(level=3, is_available=True)
            if not l3_approvers.exists():
                raise ValidationError("No available Level 3 approvers are configured.")

            approvals = [
                PaymentRequisitionApproval(
                    payment_requisition=requisition,
                    approver=profile.user,
                    level=3,
                    status='PENDING',
                )
                for profile in l3_approvers
            ]
            PaymentRequisitionApproval.objects.bulk_create(approvals)

            PaymentAuditEvent.objects.create(
                payment_requisition=requisition,
                actor=approver,
                action='L2_APPROVED',
                detail={'status': requisition.status},
            )
            transaction.on_commit(lambda: PaymentNotificationService.notify_l3_approvers(requisition))
            return requisition

    @staticmethod
    def approve_l3(requisition, approver):
        if requisition.status != PaymentRequisition.Status.L2_APPROVED:
            raise ValidationError("Requisition must be Level 2 approved before Level 3 approval.")

        approval = PaymentRequisitionApproval.objects.filter(
            payment_requisition=requisition,
            level=3,
            approver=approver,
            status='PENDING',
        ).first()
        if not approval:
            raise ValidationError("No pending Level 3 approval found for this user.")

        with transaction.atomic():
            approval.status = 'APPROVED'
            approval.approved_at = timezone.now()
            approval.save(update_fields=['status', 'approved_at'])

            requisition.status = PaymentRequisition.Status.L3_APPROVED
            requisition.approved_by = approver
            requisition.approved_date = timezone.now()
            requisition.save(update_fields=['status', 'approved_by', 'approved_date', 'updated_at'])

            PaymentAuditEvent.objects.create(
                payment_requisition=requisition,
                actor=approver,
                action='L3_APPROVED',
                detail={'status': requisition.status},
            )
            return requisition

    @staticmethod
    def reject(requisition, approver, reason):
        if not reason or not reason.strip():
            raise ValidationError("A rejection reason is required.")

        if requisition.status == PaymentRequisition.Status.SUBMITTED:
            level = 2
            action = 'L2_REJECTED'
        elif requisition.status == PaymentRequisition.Status.L2_APPROVED:
            level = 3
            action = 'L3_REJECTED'
        else:
            raise ValidationError("Only submitted requisitions can be rejected at this stage.")

        approval = PaymentRequisitionApproval.objects.filter(
            payment_requisition=requisition,
            level=level,
            approver=approver,
            status='PENDING',
        ).first()
        if not approval:
            raise ValidationError("No pending approval record found for this user.")

        with transaction.atomic():
            approval.status = 'REJECTED'
            approval.comment = reason.strip()
            approval.approved_at = timezone.now()
            approval.save(update_fields=['status', 'comment', 'approved_at'])

            requisition.status = PaymentRequisition.Status.REJECTED
            requisition.rejection_reason = reason.strip()
            requisition.save(update_fields=['status', 'rejection_reason', 'updated_at'])

            PaymentAuditEvent.objects.create(
                payment_requisition=requisition,
                actor=approver,
                action=action,
                detail={'reason': reason.strip()},
            )
            return requisition

    @staticmethod
    def mark_paid(requisition, user, payment_reference, proof_file=None):
        if requisition.status != PaymentRequisition.Status.L3_APPROVED:
            raise ValidationError("Requisition must be fully approved before payment.")

        with transaction.atomic():
            requisition.status = PaymentRequisition.Status.PAID
            requisition.payment_date = timezone.now()
            requisition.payment_reference = payment_reference
            if proof_file:
                requisition.proof_of_payment = proof_file
            requisition.save(update_fields=['status', 'payment_date', 'payment_reference', 'proof_of_payment', 'updated_at'])

            PaymentAuditEvent.objects.create(
                payment_requisition=requisition,
                actor=user,
                action='PAID',
                detail={'payment_reference': payment_reference},
            )
            transaction.on_commit(lambda: PaymentNotificationService.notify_requester_paid(requisition))
            return requisition


