from django.urls import path
from . import views

urlpatterns = [
    path("", views.trf_list, name="trf_list"),
    path("create/", views.trf_create, name="trf_create"),
    path("<int:pk>/", views.trf_detail, name="trf_detail"),
    path("<int:pk>/submit/", views.trf_submit, name="trf_submit"),
    path("<int:pk>/approve/", views.trf_approve, name="trf_approve"),
    path("<int:pk>/reject/", views.trf_reject, name="trf_reject"),
    path("<int:pk>/remediate/", views.trf_remediate, name="trf_remediate"),
    path("approver/availability/", views.set_availability, name="set_availability"),
]
