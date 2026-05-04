from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from .exceptions import TransitionError
from .forms import ExpenseFormSet, MilestoneFormSet, TRFForm
from .models import ApproverProfile, TRFRequest
from .services import ApprovalService


def _is_sales_user(user):
    return user.role == "Sales_User"


def _is_approver(user):
    return hasattr(user, "approver_profile")


@login_required
def trf_list(request):
    user = request.user

    if _is_approver(user):
        profile = user.approver_profile
        if profile.level == 2:
            trfs = TRFRequest.objects.filter(status=TRFRequest.Status.PENDING_L2).order_by("-created_at")
        else:
            trfs = TRFRequest.objects.filter(status=TRFRequest.Status.PENDING_L3).order_by("-created_at")
    else:
        trfs = TRFRequest.objects.filter(submitted_by=user).order_by("-created_at")

    return render(request, "trf/list.html", {"trfs": trfs})


@login_required
def trf_create(request):
    if not _is_sales_user(request.user):
        messages.error(request, "Only Sales Users can create TRFs.")
        return redirect("trf_list")

    if request.method == "POST":
        form = TRFForm(request.POST)
        milestone_formset = MilestoneFormSet(request.POST, prefix="milestones")
        expense_formset = ExpenseFormSet(request.POST, prefix="expenses")

        if form.is_valid() and milestone_formset.is_valid() and expense_formset.is_valid():
            trf = form.save(commit=False)
            trf.submitted_by = request.user
            trf.status = TRFRequest.Status.DRAFT
            trf.save()

            milestone_formset.instance = trf
            milestone_formset.save()

            expense_formset.instance = trf
            expense_formset.save()

            messages.success(request, "TRF created successfully.")
            return redirect("trf_detail", pk=trf.pk)
    else:
        form = TRFForm()
        milestone_formset = MilestoneFormSet(prefix="milestones")
        expense_formset = ExpenseFormSet(prefix="expenses")

    return render(request, "trf/create.html", {
        "form": form,
        "milestone_formset": milestone_formset,
        "expense_formset": expense_formset,
    })


@login_required
def trf_detail(request, pk):
    trf = get_object_or_404(TRFRequest, pk=pk)
    milestones = trf.milestones.all()
    expenses = trf.expenses.all()
    approvals = trf.approvals.all()
    audit_events = trf.audit_events.all()

    user = request.user
    can_approve = False
    can_reject = False
    can_remediate = False

    if _is_approver(user):
        profile = user.approver_profile
        if profile.is_available or (profile.delegate and profile.delegate.user == user):
            if trf.status == TRFRequest.Status.PENDING_L2 and profile.level == 2:
                can_approve = True
                can_reject = True
            elif trf.status == TRFRequest.Status.PENDING_L3 and profile.level == 3:
                can_approve = True
                can_reject = True

    if trf.status == TRFRequest.Status.REJECTED and trf.submitted_by == user:
        can_remediate = True

    total_expenses = sum(e.amount for e in expenses)

    return render(request, "trf/detail.html", {
        "trf": trf,
        "milestones": milestones,
        "expenses": expenses,
        "approvals": approvals,
        "audit_events": audit_events,
        "can_approve": can_approve,
        "can_reject": can_reject,
        "can_remediate": can_remediate,
        "total_expenses": total_expenses,
    })


@login_required
def trf_submit(request, pk):
    if request.method != "POST":
        return redirect("trf_detail", pk=pk)
    trf = get_object_or_404(TRFRequest, pk=pk)
    try:
        ApprovalService.submit(trf, request.user)
        messages.success(request, "TRF submitted for Level 2 approval.")
    except TransitionError as e:
        messages.error(request, str(e))
    return redirect("trf_detail", pk=pk)


@login_required
def trf_approve(request, pk):
    if request.method != "POST":
        return redirect("trf_detail", pk=pk)
    trf = get_object_or_404(TRFRequest, pk=pk)
    try:
        ApprovalService.approve(trf, request.user)
        messages.success(request, "TRF approved successfully.")
    except (TransitionError, PermissionError) as e:
        messages.error(request, str(e))
    return redirect("trf_detail", pk=pk)


@login_required
def trf_reject(request, pk):
    trf = get_object_or_404(TRFRequest, pk=pk)

    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        if not reason:
            return render(request, "trf/reject.html", {
                "trf": trf,
                "error": "A rejection reason is required.",
            })
        try:
            ApprovalService.reject(trf, request.user, reason)
            messages.success(request, "TRF rejected.")
            return redirect("trf_detail", pk=pk)
        except (TransitionError, PermissionError, ValueError) as e:
            return render(request, "trf/reject.html", {
                "trf": trf,
                "error": str(e),
            })

    return render(request, "trf/reject.html", {"trf": trf})


@login_required
def trf_remediate(request, pk):
    trf = get_object_or_404(TRFRequest, pk=pk)

    # Find the most recent rejection reason for display.
    last_rejection = (
        trf.approvals.filter(action="REJECTED").order_by("-acted_at").first()
    )

    if request.method == "POST":
        form = TRFForm(request.POST, instance=trf)
        if form.is_valid():
            try:
                ApprovalService.remediate(trf, request.user, form.cleaned_data)
                return redirect("trf_detail", pk=pk)
            except TransitionError as e:
                form.add_error(None, str(e))
            except ValidationError as e:
                form.add_error(None, e.message)
    else:
        form = TRFForm(instance=trf)

    return render(request, "trf/remediate.html", {
        "trf": trf,
        "form": form,
        "last_rejection": last_rejection,
    })


@login_required
def set_availability(request):
    profile = getattr(request.user, "approver_profile", None)
    if profile is None:
        messages.error(request, "You are not a named approver.")
        return redirect("trf_list")

    # Other approvers at the same level, excluding self
    same_level_approvers = ApproverProfile.objects.filter(
        level=profile.level
    ).exclude(pk=profile.pk).select_related("user")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "mark_unavailable":
            delegate_id = request.POST.get("delegate")
            if not delegate_id:
                messages.error(request, "Please select a delegate before marking yourself unavailable.")
                return render(request, "trf/availability.html", {
                    "profile": profile,
                    "same_level_approvers": same_level_approvers,
                })
            try:
                delegate_profile = same_level_approvers.get(pk=delegate_id)
            except ApproverProfile.DoesNotExist:
                messages.error(request, "Invalid delegate selection.")
                return render(request, "trf/availability.html", {
                    "profile": profile,
                    "same_level_approvers": same_level_approvers,
                })
            profile.is_available = False
            profile.delegate = delegate_profile
            profile.save(update_fields=["is_available", "delegate"])
            delegate_name = delegate_profile.user.get_full_name() or delegate_profile.user.username
            messages.success(request, f"You are now marked as unavailable. {delegate_name} will cover your queue.")
            return redirect("set_availability")

        elif action == "mark_available":
            profile.is_available = True
            profile.delegate = None
            profile.save(update_fields=["is_available", "delegate"])
            messages.success(request, "You are now marked as available.")
            return redirect("set_availability")

    return render(request, "trf/availability.html", {
        "profile": profile,
        "same_level_approvers": same_level_approvers,
    })
