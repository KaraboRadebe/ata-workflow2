import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from .certification_forms import CertificationForm
from .models import Certification
from .services import CertificationService, DashboardReportService

logger = logging.getLogger(__name__)


@login_required
def certification_list(request):
    if request.user.is_staff or request.user.system_role in {"Admin", "Finance"}:
        certifications = Certification.objects.select_related("contact").all()
    else:
        certifications = Certification.objects.filter(contact=request.user).select_related("contact")

    return render(request, "procurement/certification_list.html", {
        "certifications": certifications,
    })


@login_required
def certification_create(request):
    if request.method == "POST":
        form = CertificationForm(request.POST)
        if form.is_valid():
            try:
                certification = CertificationService.create(form.cleaned_data)
                messages.success(request, "Certification created successfully.")
                return redirect("certification_list")
            except ValidationError as exc:
                form.add_error(None, exc)
    else:
        form = CertificationForm()
    return render(request, "procurement/certification_form.html", {
        "form": form,
        "title": "Create Certification",
    })


@login_required
def certification_edit(request, pk):
    certification = get_object_or_404(Certification, pk=pk)
    if not (request.user.is_staff or request.user == certification.contact):
        return redirect("certification_list")

    if request.method == "POST":
        form = CertificationForm(request.POST, instance=certification)
        if form.is_valid():
            try:
                CertificationService.update(certification, form.cleaned_data)
                messages.success(request, "Certification updated successfully.")
                return redirect("certification_list")
            except ValidationError as exc:
                form.add_error(None, exc)
    else:
        form = CertificationForm(instance=certification)

    return render(request, "procurement/certification_form.html", {
        "form": form,
        "title": "Edit Certification",
    })


@login_required
def reports_overview(request):
    overview = DashboardReportService.overview_summary()
    return render(request, "procurement/dashboard_report.html", overview)


@login_required
def trf_cycle_time_report(request):
    data = DashboardReportService.trf_cycle_time_data()
    return render(request, "procurement/analytics_charts.html", {
        "chart_title": "TRF Cycle Time",
        "chart_labels": data["labels"],
        "chart_values": data["values"],
        "chart_type": "line",
        "summary": data["summary"],
    })


@login_required
def projects_report(request):
    data = DashboardReportService.projects_by_status()
    return render(request, "procurement/analytics_charts.html", {
        "chart_title": "Projects by Status",
        "chart_labels": data["labels"],
        "chart_values": data["values"],
        "chart_type": "bar",
        "summary": data["summary"],
    })
