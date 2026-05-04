from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .exceptions import MilestoneDeletionError, ProjectTransitionError
from .forms import MilestoneForm, ProjectStatusForm
from .models import Milestone, Project
from .permissions import is_project_manager, require_project_manager
from .services import MilestoneService, ProjectService


@login_required
def project_list(request):
    user = request.user
    if user.role == "Sales_User":
        qs = Project.objects.filter(sales_user=user).select_related("trf")
    else:
        qs = Project.objects.all().select_related("trf")

    return render(request, "projects/project_list.html", {
        "projects": qs,
        "is_project_manager": is_project_manager(user),
    })


@login_required
def project_detail(request, pk):
    project = get_object_or_404(Project.objects.select_related("trf", "sales_user"), pk=pk)
    milestones = project.milestones.order_by("target_date")
    audit_events = project.audit_events.select_related("actor").order_by("timestamp")

    # TRF Expense Summary
    trf_milestones = [m for m in milestones if m.is_trf_expense]
    total_trf_approved = sum(
        (m.original_cost_amount or Decimal("0")) for m in trf_milestones
    )
    total_current = sum(
        (m.cost_amount or Decimal("0")) for m in trf_milestones
    )
    variance = total_current - total_trf_approved

    status_form = ProjectStatusForm()

    return render(request, "projects/project_detail.html", {
        "project": project,
        "milestones": milestones,
        "audit_events": audit_events,
        "total_trf_approved": total_trf_approved,
        "total_current": total_current,
        "variance": variance,
        "status_form": status_form,
        "is_project_manager": is_project_manager(request.user),
    })


@require_project_manager
def project_status(request, pk):
    project = get_object_or_404(Project, pk=pk)

    if request.method != "POST":
        return redirect("project_detail", pk=pk)

    form = ProjectStatusForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Invalid form submission.")
        return redirect("project_detail", pk=pk)

    new_status = form.cleaned_data["new_status"]
    reason = form.cleaned_data["reason"]
    confirmed = form.cleaned_data["confirmed"]

    try:
        result = ProjectService.transition_status(
            project, request.user, new_status, reason=reason, confirmed=confirmed
        )
    except ProjectTransitionError as exc:
        messages.error(request, str(exc))
        return redirect("project_detail", pk=pk)

    if isinstance(result, dict) and result.get("warning"):
        return render(request, "projects/project_status_confirm.html", {
            "project": project,
            "incomplete_milestones": result["incomplete_milestones"],
            "new_status": new_status,
            "reason": reason,
        })

    messages.success(request, f'✅ Project status changed from {project.status} to {new_status}.')
    return redirect("project_detail", pk=pk)


@login_required
@require_project_manager
def milestone_create(request, pk):
    project = get_object_or_404(Project, pk=pk)

    if request.method == "POST":
        form = MilestoneForm(request.POST)
        if form.is_valid():
            milestone = MilestoneService.create(project, request.user, form.cleaned_data)
            messages.success(request, f'✅ Milestone "{milestone.name}" created successfully.')
            return redirect("project_detail", pk=pk)
    else:
        form = MilestoneForm()

    return render(request, "projects/milestone_form.html", {
        "form": form,
        "project": project,
        "action": "Create",
    })


@login_required
def milestone_detail(request, pk, ms_pk):
    project = get_object_or_404(Project, pk=pk)
    milestone = get_object_or_404(Milestone, pk=ms_pk, project=project)

    return render(request, "projects/milestone_detail.html", {
        "project": project,
        "milestone": milestone,
    })


@login_required
@require_project_manager
def milestone_edit(request, pk, ms_pk):
    project = get_object_or_404(Project, pk=pk)
    milestone = get_object_or_404(Milestone, pk=ms_pk, project=project)

    if request.method == "POST":
        form = MilestoneForm(request.POST, instance=milestone)
        if form.is_valid():
            updated_milestone = MilestoneService.update(milestone, request.user, form.cleaned_data)
            messages.success(request, f'✅ Milestone "{updated_milestone.name}" updated successfully.')
            return redirect("project_detail", pk=pk)
    else:
        form = MilestoneForm(instance=milestone)

    return render(request, "projects/milestone_form.html", {
        "form": form,
        "project": project,
        "milestone": milestone,
        "action": "Edit",
    })


@login_required
@require_project_manager
def milestone_delete(request, pk, ms_pk):
    project = get_object_or_404(Project, pk=pk)
    milestone = get_object_or_404(Milestone, pk=ms_pk, project=project)

    error = None
    if request.method == "POST":
        try:
            milestone_name = milestone.name
            MilestoneService.delete(milestone, request.user)
            messages.success(request, f'✅ Milestone "{milestone_name}" deleted successfully.')
            return redirect("project_detail", pk=pk)
        except MilestoneDeletionError as exc:
            error = str(exc)
            messages.error(request, f'❌ Cannot delete: {error}')

    return render(request, "projects/milestone_confirm_delete.html", {
        "project": project,
        "milestone": milestone,
        "error": error,
    })