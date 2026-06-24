import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from .payment_forms import (
    PaymentRequisitionForm,
    PaymentRequisitionPayForm,
    PaymentRequisitionRejectForm,
)
from .payment_models import PaymentRequisition, PaymentRequisitionApproval
from .payment_services import PaymentRequisitionService

logger = logging.getLogger(__name__)


def is_l2_approver(user):
    return user.is_authenticated and getattr(user, 'approval_level', '') == 'L2'


def is_l3_approver(user):
    return user.is_authenticated and getattr(user, 'approval_level', '') == 'L3'


def is_finance(user):
    return user.is_authenticated and getattr(user, 'system_role', '') == 'Finance'


def can_view_requisition(user, requisition):
    if requisition.requested_by_id == user.pk:
        return True
    if is_l2_approver(user) or is_l3_approver(user) or is_finance(user):
        return True
    return False


@login_required
def payment_requisition_list(request):
    user = request.user
    if is_l2_approver(user):
        requisitions = PaymentRequisition.objects.filter(
            approvals__approver=user,
            approvals__level=2,
        ).distinct().select_related('requested_by')
    elif is_l3_approver(user):
        requisitions = PaymentRequisition.objects.filter(
            approvals__approver=user,
            approvals__level=3,
        ).distinct().select_related('requested_by')
    elif is_finance(user):
        requisitions = PaymentRequisition.objects.select_related(
            'requested_by', 'approved_by', 'trf', 'project', 'purchase_order'
        ).all()
    else:
        requisitions = PaymentRequisition.objects.filter(
            requested_by=user
        ).select_related('requested_by', 'approved_by', 'trf', 'project', 'purchase_order')

    return render(request, 'procurement/payment_list.html', {
        'requisitions': requisitions,
        'is_l2': is_l2_approver(user),
        'is_l3': is_l3_approver(user),
        'is_finance': is_finance(user),
    })


@login_required
def payment_requisition_create(request):
    if request.method == 'POST':
        form = PaymentRequisitionForm(request.POST)
        if form.is_valid():
            try:
                requisition = PaymentRequisitionService.create(form.cleaned_data, request.user)
                messages.success(request, 'Payment requisition created.')
                return redirect('payment_requisition_detail', pk=requisition.pk)
            except ValidationError as exc:
                form.add_error(None, exc)
    else:
        form = PaymentRequisitionForm()
    return render(request, 'procurement/payment_form.html', {'form': form})


@login_required
def payment_requisition_detail(request, pk):
    requisition = get_object_or_404(
        PaymentRequisition.objects.select_related(
            'requested_by', 'approved_by', 'trf', 'project', 'purchase_order'
        ),
        pk=pk,
    )

    if not can_view_requisition(request.user, requisition):
        return HttpResponseForbidden("You do not have permission to view this payment requisition.")

    approvals = requisition.approvals.select_related('approver').order_by('level')
    audit_events = requisition.audit_events.select_related('actor').order_by('timestamp')

    can_submit = requisition.status == PaymentRequisition.Status.DRAFT and requisition.requested_by_id == request.user.pk
    can_approve_l2 = (
        is_l2_approver(request.user)
        and requisition.status == PaymentRequisition.Status.SUBMITTED
        and approvals.filter(level=2, approver=request.user, status='PENDING').exists()
    )
    can_approve_l3 = (
        is_l3_approver(request.user)
        and requisition.status == PaymentRequisition.Status.L2_APPROVED
        and approvals.filter(level=3, approver=request.user, status='PENDING').exists()
    )
    can_reject = (
        (is_l2_approver(request.user) and requisition.status == PaymentRequisition.Status.SUBMITTED)
        or (is_l3_approver(request.user) and requisition.status == PaymentRequisition.Status.L2_APPROVED)
    )
    can_pay = is_finance(request.user) and requisition.status == PaymentRequisition.Status.L3_APPROVED

    return render(request, 'procurement/payment_detail.html', {
        'requisition': requisition,
        'approvals': approvals,
        'audit_events': audit_events,
        'can_submit': can_submit,
        'can_approve_l2': can_approve_l2,
        'can_approve_l3': can_approve_l3,
        'can_reject': can_reject,
        'can_pay': can_pay,
    })


@login_required
def payment_requisition_submit(request, pk):
    requisition = get_object_or_404(PaymentRequisition, pk=pk)
    if requisition.requested_by_id != request.user.pk:
        return HttpResponseForbidden("Only the requester can submit this requisition.")

    if request.method == 'POST':
        try:
            PaymentRequisitionService.submit(requisition, request.user)
            messages.success(request, 'Payment requisition submitted for Level 2 approval.')
        except (ValidationError, PermissionError) as exc:
            messages.error(request, str(exc))
    return redirect('payment_requisition_detail', pk=pk)


@login_required
def payment_requisition_approve_l2(request, pk):
    requisition = get_object_or_404(PaymentRequisition, pk=pk)
    if not is_l2_approver(request.user):
        return HttpResponseForbidden("Only Level 2 approvers can approve this requisition.")

    if request.method == 'POST':
        try:
            PaymentRequisitionService.approve_l2(requisition, request.user)
            messages.success(request, 'Payment requisition Level 2 approved.')
        except (ValidationError, PermissionError) as exc:
            messages.error(request, str(exc))
    return redirect('payment_requisition_detail', pk=pk)


@login_required
def payment_requisition_approve_l3(request, pk):
    requisition = get_object_or_404(PaymentRequisition, pk=pk)
    if not is_l3_approver(request.user):
        return HttpResponseForbidden("Only Level 3 approvers can approve this requisition.")

    if request.method == 'POST':
        try:
            PaymentRequisitionService.approve_l3(requisition, request.user)
            messages.success(request, 'Payment requisition Level 3 approved.')
        except (ValidationError, PermissionError) as exc:
            messages.error(request, str(exc))
    return redirect('payment_requisition_detail', pk=pk)


@login_required
def payment_requisition_reject(request, pk):
    requisition = get_object_or_404(PaymentRequisition, pk=pk)
    if not ((is_l2_approver(request.user) and requisition.status == PaymentRequisition.Status.SUBMITTED)
            or (is_l3_approver(request.user) and requisition.status == PaymentRequisition.Status.L2_APPROVED)):
        return HttpResponseForbidden("Only the appropriate approver can reject this requisition.")

    if request.method == 'POST':
        form = PaymentRequisitionRejectForm(request.POST)
        if form.is_valid():
            try:
                PaymentRequisitionService.reject(requisition, request.user, form.cleaned_data['reason'])
                messages.success(request, 'Payment requisition rejected.')
                return redirect('payment_requisition_detail', pk=pk)
            except (ValidationError, PermissionError) as exc:
                messages.error(request, str(exc))
    else:
        form = PaymentRequisitionRejectForm()

    return render(request, 'procurement/payment_reject.html', {
        'requisition': requisition,
        'form': form,
    })


@login_required
def payment_requisition_pay(request, pk):
    requisition = get_object_or_404(PaymentRequisition, pk=pk)
    if not is_finance(request.user):
        return HttpResponseForbidden("Only Finance users can process payments.")

    if request.method == 'POST':
        form = PaymentRequisitionPayForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                PaymentRequisitionService.mark_paid(
                    requisition,
                    request.user,
                    form.cleaned_data['payment_reference'],
                    form.cleaned_data.get('proof_of_payment'),
                )
                messages.success(request, 'Payment requisition marked as paid.')
                return redirect('payment_requisition_detail', pk=pk)
            except (ValidationError, PermissionError) as exc:
                messages.error(request, str(exc))
    else:
        form = PaymentRequisitionPayForm()

    return render(request, 'procurement/payment_pay.html', {
        'requisition': requisition,
        'form': form,
    })


@login_required
def payment_requisition_l2_queue(request):
    if not is_l2_approver(request.user):
        return HttpResponseForbidden("Only Level 2 approvers can view the L2 queue.")

    approvals = PaymentRequisitionApproval.objects.filter(
        level=2,
        status='PENDING',
        approver=request.user,
    ).select_related('payment_requisition__requested_by', 'payment_requisition')

    return render(request, 'procurement/payment_queue.html', {
        'approvals': approvals,
        'queue_type': 'L2',
    })


@login_required
def payment_requisition_l3_queue(request):
    if not is_l3_approver(request.user):
        return HttpResponseForbidden("Only Level 3 approvers can view the L3 queue.")

    approvals = PaymentRequisitionApproval.objects.filter(
        level=3,
        status='PENDING',
        approver=request.user,
    ).select_related('payment_requisition__requested_by', 'payment_requisition')

    return render(request, 'procurement/payment_queue.html', {
        'approvals': approvals,
        'queue_type': 'L3',
    })
