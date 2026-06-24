import logging
from datetime import date, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone

from .exceptions import (
    ClientNotificationRequiredError,
    CostingSheetTransitionError,
    DuplicateCostingSheetError,
    DuplicatePOError,
    POTransitionError,
)
from .models import (
    Certification,
    CostingSheet,
    CostingSheetLineItem,
    POLineItem,
    POYearCounter,
    ProcurementAuditEvent,
    PurchaseOrder,
)
from .payment_models import PaymentRequisition
from trf.models import TRFApproval
from projects.models import Project

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ProcurementAuditService
# ---------------------------------------------------------------------------
class ProcurementAuditService:
    @staticmethod
    def record(sheet, actor, action, detail=None):
        return ProcurementAuditEvent.objects.create(
            costing_sheet=sheet,
            actor=actor,
            action=action,
            detail=detail or {},
        )


# ---------------------------------------------------------------------------
# CostingSheetService
# ---------------------------------------------------------------------------
class CostingSheetService:

    @staticmethod
    def create(project, pdr):
        if project.status != "Active":
            raise CostingSheetTransitionError(
                "Costing Sheets can only be created for Active projects."
            )
        if CostingSheet.objects.filter(project=project).exists():
            raise DuplicateCostingSheetError(
                "A Costing Sheet already exists for this project. "
                "If it was rejected, please remediate it instead of creating a new one."
            )
        if pdr.role != "PDR":
            raise PermissionError("Only PDR users can create Costing Sheets.")

        sheet = CostingSheet.objects.create(
            project=project,
            pdr=pdr,
            status=CostingSheet.Status.DRAFT,
        )
        ProcurementAuditService.record(sheet, pdr, ProcurementAuditEvent.Action.CS_CREATED)
        return sheet

    @staticmethod
    @transaction.atomic
    def submit(sheet, pdr):
        if sheet.pdr_id != pdr.pk:
            raise PermissionError("Only the PDR who created this sheet can submit it.")
        if sheet.status != CostingSheet.Status.DRAFT:
            raise CostingSheetTransitionError(
                f"Cannot submit a sheet with status '{sheet.status}'."
            )
        if not sheet.line_items.exists():
            raise ValidationError("At least one line item is required before submission.")
        missing = sheet.line_items.filter(selected_provider__isnull=True)
        if missing.exists():
            raise ValidationError(
                f"{missing.count()} line item(s) have no selected provider."
            )

        sheet.status = CostingSheet.Status.SUBMITTED
        sheet.save(update_fields=["status", "updated_at"])
        ProcurementAuditService.record(sheet, pdr, ProcurementAuditEvent.Action.CS_SUBMITTED)
        return sheet

    @staticmethod
    @transaction.atomic
    def cdr_approve(sheet, cdr):
        if cdr.role != "CDR":
            raise PermissionError("Only CDR users can approve at this stage.")
        if cdr.pk == sheet.pdr_id:
            raise PermissionError("The submitting PDR cannot also act as CDR approver.")
        if sheet.status != CostingSheet.Status.SUBMITTED:
            raise CostingSheetTransitionError(
                f"Cannot CDR-approve a sheet with status '{sheet.status}'."
            )

        # Snapshot original amounts on all line items
        for li in sheet.line_items.all():
            provider_amount = getattr(li, f"provider_{li.selected_provider}_amount", None)
            provider_currency = getattr(li, f"provider_{li.selected_provider}_currency", "")
            li.original_approved_amount = provider_amount
            li.original_approved_currency = provider_currency
            li.save(update_fields=["original_approved_amount", "original_approved_currency"])

        sheet.cdr = cdr
        sheet.status = CostingSheet.Status.CDR_APPROVED
        sheet.save(update_fields=["cdr", "status", "updated_at"])
        ProcurementAuditService.record(sheet, cdr, ProcurementAuditEvent.Action.CS_CDR_APPROVED)
        return sheet

    @staticmethod
    @transaction.atomic
    def cdr_reject(sheet, cdr, reason):
        if cdr.role != "CDR":
            raise PermissionError("Only CDR users can reject at this stage.")
        if cdr.pk == sheet.pdr_id:
            raise PermissionError("The submitting PDR cannot also act as CDR approver.")
        if sheet.status != CostingSheet.Status.SUBMITTED:
            raise CostingSheetTransitionError(
                f"Cannot CDR-reject a sheet with status '{sheet.status}'."
            )
        if not reason or not reason.strip():
            raise ValidationError("A rejection reason is required.")

        sheet.cdr = cdr
        sheet.status = CostingSheet.Status.CDR_REJECTED
        sheet.save(update_fields=["cdr", "status", "updated_at"])
        ProcurementAuditService.record(
            sheet, cdr, ProcurementAuditEvent.Action.CS_CDR_REJECTED,
            {"reason": reason.strip()}
        )
        return sheet

    @staticmethod
    @transaction.atomic
    def begin_negotiation(sheet, pdr):
        if sheet.pdr_id != pdr.pk:
            raise PermissionError("Only the sheet's PDR can begin negotiation.")
        if sheet.status != CostingSheet.Status.CDR_APPROVED:
            raise CostingSheetTransitionError(
                f"Cannot begin negotiation on a sheet with status '{sheet.status}'."
            )
        sheet.status = CostingSheet.Status.NEGOTIATING
        sheet.save(update_fields=["status", "updated_at"])
        ProcurementAuditService.record(
            sheet, pdr, ProcurementAuditEvent.Action.CS_NEGOTIATION_STARTED
        )
        return sheet

    @staticmethod
    @transaction.atomic
    def revise_quote(sheet, line_item, pdr, amount, currency):
        if sheet.pdr_id != pdr.pk:
            raise PermissionError("Only the sheet's PDR can revise quotes.")
        if sheet.status != CostingSheet.Status.NEGOTIATING:
            raise CostingSheetTransitionError(
                "Quote revision is only allowed during the Negotiating phase."
            )
        old_amount = line_item.negotiated_amount
        line_item.negotiated_amount = amount
        line_item.negotiated_currency = currency
        line_item.save(update_fields=["negotiated_amount", "negotiated_currency"])
        ProcurementAuditService.record(
            sheet, pdr, ProcurementAuditEvent.Action.CS_QUOTE_REVISED,
            {"line_item_id": str(line_item.line_item_id),
             "old_amount": str(old_amount), "new_amount": str(amount)}
        )
        return line_item

    @staticmethod
    @transaction.atomic
    def submit_for_director(sheet, pdr):
        if sheet.pdr_id != pdr.pk:
            raise PermissionError("Only the sheet's PDR can submit for Director approval.")
        if sheet.status != CostingSheet.Status.NEGOTIATING:
            raise CostingSheetTransitionError(
                f"Cannot submit for Director from status '{sheet.status}'."
            )
        sheet.status = CostingSheet.Status.SUBMITTED_FOR_DIRECTOR
        sheet.save(update_fields=["status", "updated_at"])
        ProcurementAuditService.record(
            sheet, pdr, ProcurementAuditEvent.Action.CS_SUBMITTED_DIRECTOR
        )
        return sheet

    @staticmethod
    @transaction.atomic
    def director_approve(sheet, director, justification=""):
        if not is_director_manager_role(director):
            raise PermissionError("Only Director/Manager users can approve at this stage.")
        if sheet.cdr_id and sheet.cdr_id == director.pk:
            raise PermissionError(
                "The CDR approver cannot also act as Director approver on the same sheet."
            )
        if sheet.status != CostingSheet.Status.SUBMITTED_FOR_DIRECTOR:
            raise CostingSheetTransitionError(
                f"Cannot Director-approve a sheet with status '{sheet.status}'."
            )
        # Justification required if any negotiated amount exceeds original
        needs_justification = sheet.line_items.filter(
            negotiated_amount__isnull=False,
            original_approved_amount__isnull=False,
        ).extra(where=["negotiated_amount > original_approved_amount"]).exists()

        if needs_justification and not (justification and justification.strip()):
            raise ValidationError(
                "A justification is required when negotiated amounts exceed the CDR-approved amounts."
            )

        sheet.director = director
        sheet.status = CostingSheet.Status.DIRECTOR_APPROVED
        sheet.save(update_fields=["director", "status", "updated_at"])
        ProcurementAuditService.record(
            sheet, director, ProcurementAuditEvent.Action.CS_DIRECTOR_APPROVED,
            {"justification": justification}
        )
        # Link milestones
        CostingSheetService._link_milestones(sheet)
        return sheet

    @staticmethod
    @transaction.atomic
    def director_reject(sheet, director, reason):
        if not is_director_manager_role(director):
            raise PermissionError("Only Director/Manager users can reject at this stage.")
        if sheet.cdr_id and sheet.cdr_id == director.pk:
            raise PermissionError(
                "The CDR approver cannot also act as Director approver on the same sheet."
            )
        if sheet.status != CostingSheet.Status.SUBMITTED_FOR_DIRECTOR:
            raise CostingSheetTransitionError(
                f"Cannot Director-reject a sheet with status '{sheet.status}'."
            )
        if not reason or not reason.strip():
            raise ValidationError("A rejection reason is required.")

        sheet.director = director
        sheet.status = CostingSheet.Status.DIRECTOR_REJECTED
        sheet.save(update_fields=["director", "status", "updated_at"])
        ProcurementAuditService.record(
            sheet, director, ProcurementAuditEvent.Action.CS_DIRECTOR_REJECTED,
            {"reason": reason.strip()}
        )
        return sheet

    @staticmethod
    @transaction.atomic
    def remediate(sheet, pdr):
        """CDR_Rejected → Draft."""
        if sheet.pdr_id != pdr.pk:
            raise PermissionError("Only the sheet's PDR can remediate.")
        if sheet.status != CostingSheet.Status.CDR_REJECTED:
            raise CostingSheetTransitionError(
                f"Cannot remediate from status '{sheet.status}'. Expected CDR_Rejected."
            )
        sheet.status = CostingSheet.Status.DRAFT
        sheet.save(update_fields=["status", "updated_at"])
        ProcurementAuditService.record(sheet, pdr, ProcurementAuditEvent.Action.CS_REMEDIATED)
        return sheet

    @staticmethod
    @transaction.atomic
    def remediate_after_director(sheet, pdr):
        """Director_Rejected → Negotiating (PDR retains negotiated amounts)."""
        if sheet.pdr_id != pdr.pk:
            raise PermissionError("Only the sheet's PDR can remediate.")
        if sheet.status != CostingSheet.Status.DIRECTOR_REJECTED:
            raise CostingSheetTransitionError(
                f"Cannot remediate from status '{sheet.status}'. Expected Director_Rejected."
            )
        sheet.status = CostingSheet.Status.NEGOTIATING
        sheet.save(update_fields=["status", "updated_at"])
        ProcurementAuditService.record(sheet, pdr, ProcurementAuditEvent.Action.CS_REMEDIATED)
        return sheet

    @staticmethod
    def _link_milestones(sheet):
        """Write costing sheet data back to Phase 2 Milestones on Director approval."""
        from projects.models import Milestone
        for li in sheet.line_items.all():
            try:
                milestone = Milestone.objects.get(
                    costing_sheet_line_item_id=str(li.line_item_id)
                )
                milestone.original_cost_amount = li.selected_amount
                milestone.original_currency = li.selected_currency
                milestone.save(update_fields=["original_cost_amount", "original_currency"])
            except Milestone.DoesNotExist:
                logger.warning(
                    "No milestone found for line_item_id=%s on sheet id=%s",
                    li.line_item_id, sheet.pk
                )


# ---------------------------------------------------------------------------
# POService
# ---------------------------------------------------------------------------
class POService:

    @staticmethod
    def _generate_po_number(year):
        with transaction.atomic():
            row, _ = POYearCounter.objects.select_for_update().get_or_create(
                year=year, prefix="PO", defaults={"counter": 0}
            )
            row.counter += 1
            row.save(update_fields=["counter"])
            return f"PO-{year}-{row.counter:04d}"

    @staticmethod
    @transaction.atomic
    def generate(costing_sheet, pdr):
        if pdr.role != "PDR":
            raise PermissionError("Only PDR users can generate Purchase Orders.")
        if costing_sheet.status != CostingSheet.Status.DIRECTOR_APPROVED:
            raise CostingSheetTransitionError(
                "A PO can only be generated from a Director-Approved Costing Sheet."
            )
        # Check for existing non-cancelled PO
        existing = costing_sheet.purchase_orders.exclude(
            status=PurchaseOrder.Status.CANCELLED
        ).first()
        if existing:
            raise DuplicatePOError(
                f"An active PO ({existing.po_number}) already exists for this Costing Sheet."
            )

        po_number = POService._generate_po_number(timezone.now().year)
        po = PurchaseOrder.objects.create(
            costing_sheet=costing_sheet,
            po_number=po_number,
            status=PurchaseOrder.Status.DRAFT,
            pdr=pdr,
        )

        # Create PO line items from costing sheet line items
        from projects.models import Milestone
        for li in costing_sheet.line_items.all():
            # Default expected delivery date from linked milestone
            expected_date = costing_sheet.project.trf.training_start
            try:
                milestone = Milestone.objects.get(
                    costing_sheet_line_item_id=str(li.line_item_id)
                )
                expected_date = milestone.target_date
            except Milestone.DoesNotExist:
                pass

            POLineItem.objects.create(
                purchase_order=po,
                costing_sheet_line_item=li,
                expected_delivery_date=expected_date,
            )

        ProcurementAuditService.record(
            costing_sheet, pdr, ProcurementAuditEvent.Action.PO_GENERATED,
            {"po_number": po_number}
        )
        return po

    @staticmethod
    @transaction.atomic
    def mark_issued(po, pdr):
        if pdr.role != "PDR":
            raise PermissionError("Only PDR users can issue Purchase Orders.")
        if po.status != PurchaseOrder.Status.DRAFT:
            raise POTransitionError(f"Cannot issue a PO with status '{po.status}'.")
        po.status = PurchaseOrder.Status.ISSUED
        po.issued_at = timezone.now()
        po.save(update_fields=["status", "issued_at", "updated_at"])
        ProcurementAuditService.record(
            po.costing_sheet, pdr, ProcurementAuditEvent.Action.PO_ISSUED,
            {"po_number": po.po_number}
        )
        return po

    @staticmethod
    @transaction.atomic
    def mark_fulfilled(po, pdr):
        if pdr.role != "PDR":
            raise PermissionError("Only PDR users can fulfil Purchase Orders.")
        if po.status != PurchaseOrder.Status.ISSUED:
            raise POTransitionError(f"Cannot fulfil a PO with status '{po.status}'.")
        # Block if any line item requires client notification
        blocking = po.line_items.filter(notify_client_required=True)
        if blocking.exists():
            raise ClientNotificationRequiredError(
                f"{blocking.count()} line item(s) require client notification before fulfilment."
            )
        po.status = PurchaseOrder.Status.FULFILLED
        po.fulfilled_at = timezone.now()
        po.save(update_fields=["status", "fulfilled_at", "updated_at"])
        ProcurementAuditService.record(
            po.costing_sheet, pdr, ProcurementAuditEvent.Action.PO_FULFILLED,
            {"po_number": po.po_number}
        )
        return po

    @staticmethod
    @transaction.atomic
    def cancel(po, pdr, reason):
        if pdr.role != "PDR":
            raise PermissionError("Only PDR users can cancel Purchase Orders.")
        if po.status == PurchaseOrder.Status.FULFILLED:
            raise POTransitionError("Fulfilled Purchase Orders cannot be cancelled.")
        po.status = PurchaseOrder.Status.CANCELLED
        po.cancelled_at = timezone.now()
        po.cancellation_reason = reason
        po.save(update_fields=["status", "cancelled_at", "cancellation_reason", "updated_at"])
        ProcurementAuditService.record(
            po.costing_sheet, pdr, ProcurementAuditEvent.Action.PO_CANCELLED,
            {"po_number": po.po_number, "reason": reason}
        )
        return po

    @staticmethod
    @transaction.atomic
    def record_eta(po_line_item, pdr, eta_date):
        if pdr.role != "PDR":
            raise PermissionError("Only PDR users can record ETAs.")
        previous_eta = po_line_item.supplier_eta
        po_line_item.supplier_eta = eta_date
        if previous_eta and abs((eta_date - previous_eta).days) > 7:
            po_line_item.notify_client_required = True
        po_line_item.save(update_fields=["supplier_eta", "notify_client_required"])
        action = (ProcurementAuditEvent.Action.ETA_UPDATED
                  if previous_eta else ProcurementAuditEvent.Action.ETA_RECORDED)
        ProcurementAuditService.record(
            po_line_item.purchase_order.costing_sheet, pdr, action,
            {"previous_eta": str(previous_eta) if previous_eta else None,
             "new_eta": str(eta_date)}
        )
        return po_line_item

    @staticmethod
    @transaction.atomic
    def record_actual_delivery(po_line_item, pdr, delivery_date):
        if pdr.role != "PDR":
            raise PermissionError("Only PDR users can record delivery dates.")
        po_line_item.actual_delivery_date = delivery_date
        po_line_item.save(update_fields=["actual_delivery_date"])
        ProcurementAuditService.record(
            po_line_item.purchase_order.costing_sheet, pdr,
            ProcurementAuditEvent.Action.DELIVERY_RECORDED,
            {"delivery_date": str(delivery_date)}
        )
        return po_line_item


def is_director_manager_role(user):
    return user.role in {"Director", "Admin"}


class CertificationService:
    REMINDER_THRESHOLDS = [90, 60, 30]

    @staticmethod
    def create(cleaned_data):
        certification = Certification.objects.create(
            contact=cleaned_data["contact"],
            certification_type=cleaned_data["certification_type"],
            issue_date=cleaned_data["issue_date"],
            expiry_date=cleaned_data.get("expiry_date"),
        )
        return certification

    @staticmethod
    def update(certification, cleaned_data):
        certification.contact = cleaned_data["contact"]
        certification.certification_type = cleaned_data["certification_type"]
        certification.issue_date = cleaned_data["issue_date"]
        certification.expiry_date = cleaned_data.get("expiry_date")
        certification.save()
        return certification

    @staticmethod
    def send_expiry_reminders():
        today = date.today()
        reminders_sent = 0

        for threshold in CertificationService.REMINDER_THRESHOLDS:
            target_date = today + timedelta(days=threshold)
            certifications = Certification.objects.filter(
                expiry_date=target_date,
            ).exclude(
                reminder_sent_at__date=today,
            )
            for certification in certifications:
                CertificationService._send_reminder(certification, threshold)
                reminders_sent += 1

        return reminders_sent

    @staticmethod
    def _send_reminder(certification, days_before):
        recipient = certification.contact.email or certification.contact.username
        subject = f"Certification expires in {days_before} days: {certification.certification_type}"
        body = (
            f"Hello {certification.contact.get_full_name() or certification.contact.username},\n\n"
            f"Your {certification.certification_type} certification expires on {certification.expiry_date}.\n"
            f"Please arrange renewal before the expiry date.\n\n"
            f"This is a reminder sent {days_before} days before expiry.\n"
        )
        try:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=False)
        except Exception:
            logger.exception("Failed to send certification reminder to %s", recipient)
        certification.reminder_sent = True
        certification.reminder_sent_at = timezone.now()
        certification.save(update_fields=["reminder_sent", "reminder_sent_at"])


class DashboardReportService:
    @staticmethod
    def overview_summary():
        project_status = DashboardReportService.projects_by_status()
        payment_status = DashboardReportService.payment_requisition_status()
        procurement_summary = DashboardReportService.procurement_summary()
        cycle_data = DashboardReportService.trf_cycle_time_data()

        return {
            "project_status_counts": project_status["summary"],
            "payment_status_counts": payment_status["summary"],
            "procurement_summary": procurement_summary,
            "trf_cycle_average": cycle_data["average_days"],
            "trf_cycle_labels": cycle_data["labels"],
            "trf_cycle_values": cycle_data["values"],
        }

    @staticmethod
    def trf_cycle_time_data():
        approvals = TRFApproval.objects.filter(
            level=TRFApproval.Level.L3,
            action=TRFApproval.Action.APPROVED,
        ).select_related("trf")
        durations = []
        for approval in approvals:
            if approval.trf.submitted_at:
                delta = approval.acted_at.date() - approval.trf.submitted_at.date()
                durations.append(delta.days)

        labels = [f"TRF {idx + 1}" for idx in range(len(durations))]
        return {
            "labels": labels,
            "values": durations,
            "average_days": sum(durations) / len(durations) if durations else 0,
            "summary": {
                "total_approved": len(durations),
                "average_days": round(sum(durations) / len(durations), 1) if durations else 0,
            },
        }

    @staticmethod
    def projects_by_status():
        counts = Project.objects.values("status").annotate(count=Count("pk"))
        summary = {item["status"]: item["count"] for item in counts}
        return {
            "labels": list(summary.keys()),
            "values": list(summary.values()),
            "summary": summary,
        }

    @staticmethod
    def payment_requisition_status():
        counts = PaymentRequisition.objects.values("status").annotate(count=Count("pk"))
        summary = {item["status"]: item["count"] for item in counts}
        return {
            "labels": list(summary.keys()),
            "values": list(summary.values()),
            "summary": summary,
        }

    @staticmethod
    def procurement_summary():
        sheet_counts = CostingSheet.objects.values("status").annotate(count=Count("pk"))
        po_counts = PurchaseOrder.objects.values("status").annotate(count=Count("pk"))
        return {
            "costing_sheets": {item["status"]: item["count"] for item in sheet_counts},
            "purchase_orders": {item["status"]: item["count"] for item in po_counts},
        }
