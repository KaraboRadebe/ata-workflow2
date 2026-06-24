from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from projects.models import Project
from .exceptions import (
    ClientNotificationRequiredError,
    CostingSheetTransitionError,
    DuplicateCostingSheetError,
    DuplicatePOError,
    POTransitionError,
)
from .forms import (
    DeliveryForm, DirectorApproveForm, ETAForm,
    LineItemForm, POCancelForm, RejectForm, ReviseQuoteForm,
)
from .models import CostingSheet, CostingSheetLineItem, POLineItem, PurchaseOrder
from .payment_views import (
    payment_requisition_list,
    payment_requisition_create,
    payment_requisition_detail,
    payment_requisition_submit,
    payment_requisition_approve_l2,
    payment_requisition_approve_l3,
    payment_requisition_reject,
    payment_requisition_pay,
    payment_requisition_l2_queue,
    payment_requisition_l3_queue,
)
from .permissions import is_cdr, is_director_manager, is_pdr
from .services import CostingSheetService, POService


# ── Costing Sheet list ──────────────────────────────────────────────────────

@login_required
def cs_list(request):
    user = request.user
    if is_pdr(user):
        sheets = CostingSheet.objects.filter(pdr=user).select_related("project")
    elif is_cdr(user):
        sheets = CostingSheet.objects.all().select_related("project")
    else:
        sheets = CostingSheet.objects.all().select_related("project")
    return render(request, "procurement/cs_list.html", {"sheets": sheets})


# ── Create Costing Sheet ────────────────────────────────────────────────────

@login_required
def cs_create(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if request.method == "POST":
        try:
            sheet = CostingSheetService.create(project, request.user)
            messages.success(request, "Costing Sheet created.")
            return redirect("cs_detail", pk=sheet.pk)
        except (CostingSheetTransitionError, DuplicateCostingSheetError, PermissionError) as e:
            messages.error(request, str(e))
    return render(request, "procurement/cs_create.html", {"project": project})


# ── Costing Sheet detail ────────────────────────────────────────────────────

@login_required
def cs_detail(request, pk):
    sheet = get_object_or_404(CostingSheet.objects.select_related("project", "pdr", "cdr", "director"), pk=pk)
    line_items = sheet.line_items.all()
    audit_events = sheet.audit_events.select_related("actor").order_by("timestamp")
    po = sheet.purchase_orders.exclude(status="Cancelled").first()
    return render(request, "procurement/cs_detail.html", {
        "sheet": sheet,
        "line_items": line_items,
        "audit_events": audit_events,
        "po": po,
        "is_pdr": is_pdr(request.user),
        "is_cdr": is_cdr(request.user),
        "is_director": is_director_manager(request.user),
        "is_owner": sheet.pdr_id == request.user.pk,
    })


# ── State transitions ───────────────────────────────────────────────────────

@login_required
def cs_submit(request, pk):
    sheet = get_object_or_404(CostingSheet, pk=pk)
    if request.method == "POST":
        try:
            CostingSheetService.submit(sheet, request.user)
            messages.success(request, "Costing Sheet submitted for CDR approval.")
        except (CostingSheetTransitionError, ValidationError, PermissionError) as e:
            messages.error(request, str(e))
    return redirect("cs_detail", pk=pk)


@login_required
def cs_cdr_approve(request, pk):
    sheet = get_object_or_404(CostingSheet, pk=pk)
    if request.method == "POST":
        try:
            CostingSheetService.cdr_approve(sheet, request.user)
            messages.success(request, "Costing Sheet CDR-approved. PDR can now begin negotiation.")
        except (CostingSheetTransitionError, PermissionError) as e:
            messages.error(request, str(e))
    return redirect("cs_detail", pk=pk)


@login_required
def cs_cdr_reject(request, pk):
    sheet = get_object_or_404(CostingSheet, pk=pk)
    if request.method == "POST":
        form = RejectForm(request.POST)
        if form.is_valid():
            try:
                CostingSheetService.cdr_reject(sheet, request.user, form.cleaned_data["reason"])
                messages.success(request, "Costing Sheet rejected.")
                return redirect("cs_detail", pk=pk)
            except (CostingSheetTransitionError, ValidationError, PermissionError) as e:
                messages.error(request, str(e))
    else:
        form = RejectForm()
    return render(request, "procurement/cs_reject.html", {"sheet": sheet, "form": form, "stage": "CDR"})


@login_required
def cs_begin_negotiation(request, pk):
    sheet = get_object_or_404(CostingSheet, pk=pk)
    if request.method == "POST":
        try:
            CostingSheetService.begin_negotiation(sheet, request.user)
            messages.success(request, "Negotiation phase started.")
        except (CostingSheetTransitionError, PermissionError) as e:
            messages.error(request, str(e))
    return redirect("cs_detail", pk=pk)


@login_required
def cs_revise_quote(request, pk):
    sheet = get_object_or_404(CostingSheet, pk=pk)
    if request.method == "POST":
        form = ReviseQuoteForm(request.POST)
        if form.is_valid():
            li = get_object_or_404(CostingSheetLineItem, pk=form.cleaned_data["line_item_id"], costing_sheet=sheet)
            try:
                CostingSheetService.revise_quote(
                    sheet, li, request.user,
                    form.cleaned_data["amount"], form.cleaned_data["currency"]
                )
                messages.success(request, "Quote revised.")
            except (CostingSheetTransitionError, PermissionError) as e:
                messages.error(request, str(e))
    return redirect("cs_detail", pk=pk)


@login_required
def cs_submit_for_director(request, pk):
    sheet = get_object_or_404(CostingSheet, pk=pk)
    if request.method == "POST":
        try:
            CostingSheetService.submit_for_director(sheet, request.user)
            messages.success(request, "Submitted for Director approval.")
        except (CostingSheetTransitionError, PermissionError) as e:
            messages.error(request, str(e))
    return redirect("cs_detail", pk=pk)


@login_required
def cs_director_approve(request, pk):
    sheet = get_object_or_404(CostingSheet, pk=pk)
    if request.method == "POST":
        form = DirectorApproveForm(request.POST)
        if form.is_valid():
            try:
                CostingSheetService.director_approve(
                    sheet, request.user, form.cleaned_data.get("justification", "")
                )
                messages.success(request, "Costing Sheet fully approved. PO can now be generated.")
                return redirect("cs_detail", pk=pk)
            except (CostingSheetTransitionError, ValidationError, PermissionError) as e:
                messages.error(request, str(e))
    else:
        form = DirectorApproveForm()
    return render(request, "procurement/cs_director_approve.html", {
        "sheet": sheet,
        "form": form,
        "line_items": sheet.line_items.all(),
    })


@login_required
def cs_director_reject(request, pk):
    sheet = get_object_or_404(CostingSheet, pk=pk)
    if request.method == "POST":
        form = RejectForm(request.POST)
        if form.is_valid():
            try:
                CostingSheetService.director_reject(sheet, request.user, form.cleaned_data["reason"])
                messages.success(request, "Costing Sheet rejected by Director.")
                return redirect("cs_detail", pk=pk)
            except (CostingSheetTransitionError, ValidationError, PermissionError) as e:
                messages.error(request, str(e))
    else:
        form = RejectForm()
    return render(request, "procurement/cs_reject.html", {"sheet": sheet, "form": form, "stage": "Director"})


@login_required
def cs_remediate(request, pk):
    sheet = get_object_or_404(CostingSheet, pk=pk)
    if request.method == "POST":
        try:
            if sheet.status == CostingSheet.Status.CDR_REJECTED:
                CostingSheetService.remediate(sheet, request.user)
                messages.success(request, "Costing Sheet returned to Draft for revision.")
            elif sheet.status == CostingSheet.Status.DIRECTOR_REJECTED:
                CostingSheetService.remediate_after_director(sheet, request.user)
                messages.success(request, "Costing Sheet returned to Negotiating phase.")
        except (CostingSheetTransitionError, PermissionError) as e:
            messages.error(request, str(e))
    return redirect("cs_detail", pk=pk)


# ── Line Items ──────────────────────────────────────────────────────────────

@login_required
def li_add(request, pk):
    sheet = get_object_or_404(CostingSheet, pk=pk)
    if request.method == "POST":
        form = LineItemForm(request.POST)
        if form.is_valid():
            if sheet.status != CostingSheet.Status.DRAFT:
                messages.error(request, "Line items can only be added to Draft sheets.")
                return redirect("cs_detail", pk=pk)
            li = form.save(commit=False)
            li.costing_sheet = sheet
            li.saved_by = request.user
            li.save()
            messages.success(request, "Line item added.")
            return redirect("cs_detail", pk=pk)
    else:
        form = LineItemForm()
    return render(request, "procurement/li_form.html", {"form": form, "sheet": sheet, "action": "Add"})


@login_required
def li_edit(request, pk, li_pk):
    sheet = get_object_or_404(CostingSheet, pk=pk)
    li = get_object_or_404(CostingSheetLineItem, pk=li_pk, costing_sheet=sheet)
    if request.method == "POST":
        form = LineItemForm(request.POST, instance=li)
        if form.is_valid():
            if sheet.status != CostingSheet.Status.DRAFT:
                messages.error(request, "Line items can only be edited on Draft sheets.")
                return redirect("cs_detail", pk=pk)
            updated = form.save(commit=False)
            updated.saved_by = request.user
            updated.save()
            messages.success(request, "Line item updated.")
            return redirect("cs_detail", pk=pk)
    else:
        form = LineItemForm(instance=li)
    return render(request, "procurement/li_form.html", {"form": form, "sheet": sheet, "li": li, "action": "Edit"})


@login_required
def li_delete(request, pk, li_pk):
    sheet = get_object_or_404(CostingSheet, pk=pk)
    li = get_object_or_404(CostingSheetLineItem, pk=li_pk, costing_sheet=sheet)
    if request.method == "POST":
        if sheet.status != CostingSheet.Status.DRAFT:
            messages.error(request, "Line items can only be deleted from Draft sheets.")
        else:
            li.delete()
            messages.success(request, "Line item deleted.")
    return redirect("cs_detail", pk=pk)


# ── Purchase Orders ─────────────────────────────────────────────────────────

@login_required
def po_generate(request, pk):
    sheet = get_object_or_404(CostingSheet, pk=pk)
    if request.method == "POST":
        try:
            po = POService.generate(sheet, request.user)
            messages.success(request, f"Purchase Order {po.po_number} generated.")
            return redirect("po_detail", po_pk=po.pk)
        except (CostingSheetTransitionError, DuplicatePOError, PermissionError) as e:
            messages.error(request, str(e))
    return redirect("cs_detail", pk=pk)


@login_required
def po_detail(request, po_pk):
    po = get_object_or_404(PurchaseOrder.objects.select_related("costing_sheet", "pdr"), pk=po_pk)
    line_items = po.line_items.select_related("costing_sheet_line_item").all()
    audit_events = po.costing_sheet.audit_events.filter(
        action__in=["PO_GENERATED", "PO_ISSUED", "PO_FULFILLED", "PO_CANCELLED",
                    "ETA_RECORDED", "ETA_UPDATED", "DELIVERY_RECORDED", "CLIENT_NOTIFIED"]
    ).select_related("actor").order_by("timestamp")
    all_delivered = all(li.actual_delivery_date for li in line_items)
    return render(request, "procurement/po_detail.html", {
        "po": po,
        "line_items": line_items,
        "audit_events": audit_events,
        "is_pdr": is_pdr(request.user),
        "all_delivered": all_delivered,
        "eta_form": ETAForm(),
        "delivery_form": DeliveryForm(),
        "cancel_form": POCancelForm(),
    })


@login_required
def po_issue(request, po_pk):
    po = get_object_or_404(PurchaseOrder, pk=po_pk)
    if request.method == "POST":
        try:
            POService.mark_issued(po, request.user)
            messages.success(request, f"PO {po.po_number} issued to supplier.")
        except (POTransitionError, PermissionError) as e:
            messages.error(request, str(e))
    return redirect("po_detail", po_pk=po_pk)


@login_required
def po_fulfill(request, po_pk):
    po = get_object_or_404(PurchaseOrder, pk=po_pk)
    if request.method == "POST":
        try:
            POService.mark_fulfilled(po, request.user)
            messages.success(request, f"PO {po.po_number} marked as fulfilled.")
        except (POTransitionError, ClientNotificationRequiredError, PermissionError) as e:
            messages.error(request, str(e))
    return redirect("po_detail", po_pk=po_pk)


@login_required
def po_cancel(request, po_pk):
    po = get_object_or_404(PurchaseOrder, pk=po_pk)
    if request.method == "POST":
        form = POCancelForm(request.POST)
        if form.is_valid():
            try:
                POService.cancel(po, request.user, form.cleaned_data["reason"])
                messages.success(request, f"PO {po.po_number} cancelled.")
                return redirect("cs_detail", pk=po.costing_sheet_id)
            except (POTransitionError, PermissionError) as e:
                messages.error(request, str(e))
    return redirect("po_detail", po_pk=po_pk)


@login_required
def po_li_eta(request, po_pk, li_pk):
    po = get_object_or_404(PurchaseOrder, pk=po_pk)
    li = get_object_or_404(POLineItem, pk=li_pk, purchase_order=po)
    if request.method == "POST":
        form = ETAForm(request.POST)
        if form.is_valid():
            try:
                POService.record_eta(li, request.user, form.cleaned_data["eta_date"])
                messages.success(request, "Supplier ETA recorded.")
            except PermissionError as e:
                messages.error(request, str(e))
    return redirect("po_detail", po_pk=po_pk)


@login_required
def po_li_delivery(request, po_pk, li_pk):
    po = get_object_or_404(PurchaseOrder, pk=po_pk)
    li = get_object_or_404(POLineItem, pk=li_pk, purchase_order=po)
    if request.method == "POST":
        form = DeliveryForm(request.POST)
        if form.is_valid():
            try:
                POService.record_actual_delivery(li, request.user, form.cleaned_data["delivery_date"])
                messages.success(request, "Actual delivery date recorded.")
            except PermissionError as e:
                messages.error(request, str(e))
    return redirect("po_detail", po_pk=po_pk)


# ── Phase 4: Stock & Delivery ───────────────────────────────────────────────

from .stock_models import DeliveryDocument, ProofOfDelivery, StockMovement


@login_required
def doc_upload(request, po_pk):
    """Upload stock photos, COAS, or compliance documents for a PO."""
    po = get_object_or_404(PurchaseOrder, pk=po_pk)
    if request.method == "POST" and request.FILES.get("file"):
        doc_type = request.POST.get("doc_type", "Photo")
        description = request.POST.get("description", "")
        DeliveryDocument.objects.create(
            purchase_order=po,
            doc_type=doc_type,
            file=request.FILES["file"],
            description=description,
            uploaded_by=request.user,
        )
        messages.success(request, "Document uploaded successfully.")
    return redirect("po_detail", po_pk=po_pk)


@login_required
def pod_upload(request, po_pk):
    """Upload signed Proof of Delivery."""
    po = get_object_or_404(PurchaseOrder, pk=po_pk)
    if request.method == "POST" and request.FILES.get("pod_file"):
        signed_by = request.POST.get("signed_by", "").strip()
        signed_at = request.POST.get("signed_at", "")
        notes = request.POST.get("notes", "")
        existing_pod = getattr(po, "pod", None)
        if not signed_by or not signed_at:
            messages.error(request, "Signed by and signed date are required.")
        else:
            ProofOfDelivery.objects.update_or_create(
                purchase_order=po,
                defaults={
                    "pod_file": request.FILES["pod_file"],
                    "signed_by": signed_by,
                    "signed_at": signed_at,
                    "signature_data": existing_pod.signature_data if existing_pod else "",
                    "notes": notes,
                    "uploaded_by": request.user,
                }
            )
            messages.success(request, "Proof of Delivery uploaded.")
    return redirect("po_detail", po_pk=po_pk)


@login_required
def stock_update(request, po_pk, li_pk):
    """Update stock movement stage for a PO line item."""
    po = get_object_or_404(PurchaseOrder, pk=po_pk)
    li = get_object_or_404(POLineItem, pk=li_pk, purchase_order=po)
    if request.method == "POST":
        new_stage = request.POST.get("stage")
        notes = request.POST.get("notes", "")
        signed_by = request.POST.get("signed_by", "").strip()
        signature_data = request.POST.get("signature_data", "").strip()

        # Validate: cannot mark Delivered without at least one photo/COAS
        if new_stage == StockMovement.Stage.DELIVERED:
            has_docs = po.delivery_documents.filter(
                doc_type__in=["Photo", "COAS"]
            ).exists()
            if not has_docs:
                messages.error(
                    request,
                    "Cannot mark as Delivered — upload stock photos or COAS documents first."
                )
                return redirect("po_detail", po_pk=po_pk)

            if not signature_data:
                messages.error(
                    request,
                    "A delivery signature is required to mark stock as Delivered."
                )
                return redirect("po_detail", po_pk=po_pk)

            signed_by = signed_by or request.user.get_full_name() or request.user.username
            existing_pod = getattr(po, "pod", None)
            ProofOfDelivery.objects.update_or_create(
                purchase_order=po,
                defaults={
                    "pod_file": existing_pod.pod_file if existing_pod else None,
                    "signed_by": signed_by,
                    "signed_at": date.today(),
                    "signature_data": signature_data,
                    "notes": notes,
                    "uploaded_by": request.user,
                }
            )

        StockMovement.objects.update_or_create(
            po_line_item=li,
            defaults={"stage": new_stage, "notes": notes, "updated_by": request.user}
        )
        messages.success(request, f"Stock status updated to {new_stage}.")
    return redirect("po_detail", po_pk=po_pk)
