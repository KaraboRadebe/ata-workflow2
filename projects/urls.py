from django.urls import path
from . import views

urlpatterns = [
    path("", views.project_list, name="project_list"),
    path("<int:pk>/", views.project_detail, name="project_detail"),
    path("<int:pk>/status/", views.project_status, name="project_status"),
    path("<int:pk>/milestones/create/", views.milestone_create, name="milestone_create"),
    path("<int:pk>/milestones/<int:ms_pk>/", views.milestone_detail, name="milestone_detail"),
    path("<int:pk>/milestones/<int:ms_pk>/edit/", views.milestone_edit, name="milestone_edit"),
    path("<int:pk>/milestones/<int:ms_pk>/delete/", views.milestone_delete, name="milestone_delete"),
]
