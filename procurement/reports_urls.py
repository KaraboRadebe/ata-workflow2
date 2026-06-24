from django.urls import path

from . import phase6_views

urlpatterns = [
    path("overview/", phase6_views.reports_overview, name="reports_overview"),
    path("trf-cycle-time/", phase6_views.trf_cycle_time_report, name="reports_trf_cycle_time"),
    path("projects/", phase6_views.projects_report, name="reports_projects"),
]
