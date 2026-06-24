from django.urls import path

from . import phase6_views

urlpatterns = [
    path("", phase6_views.certification_list, name="certification_list"),
    path("create/", phase6_views.certification_create, name="certification_create"),
    path("<int:pk>/edit/", phase6_views.certification_edit, name="certification_edit"),
]
