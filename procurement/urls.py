from django.urls import path
from . import views

urlpatterns = [
    # Costing Sheets
    path("", views.cs_list, name="cs_list"),
    path("create/<int:project_pk>/", views.cs_create, name="cs_create"),
    path("<int:pk>/", views.cs_detail, name="cs_detail"),
    path("<int:pk>/submit/", views.cs_submit, name="cs_submit"),
    path("<int:pk>/cdr-approve/", views.cs_cdr_approve, name="cs_cdr_approve"),
    path("<int:pk>/cdr-reject/", views.cs_cdr_reject, name="cs_cdr_reject"),
    path("<int:pk>/begin-negotiation/", views.cs_begin_negotiation, name="cs_begin_negotiation"),
    path("<int:pk>/revise-quote/", views.cs_revise_quote, name="cs_revise_quote"),
    path("<int:pk>/submit-for-director/", views.cs_submit_for_director, name="cs_submit_for_director"),
    path("<int:pk>/director-approve/", views.cs_director_approve, name="cs_director_approve"),
    path("<int:pk>/director-reject/", views.cs_director_reject, name="cs_director_reject"),
    path("<int:pk>/remediate/", views.cs_remediate, name="cs_remediate"),
    # Line Items
    path("<int:pk>/line-items/add/", views.li_add, name="li_add"),
    path("<int:pk>/line-items/<int:li_pk>/edit/", views.li_edit, name="li_edit"),
    path("<int:pk>/line-items/<int:li_pk>/delete/", views.li_delete, name="li_delete"),
    # Purchase Orders
    path("<int:pk>/po/generate/", views.po_generate, name="po_generate"),
    path("po/<int:po_pk>/", views.po_detail, name="po_detail"),
    path("po/<int:po_pk>/issue/", views.po_issue, name="po_issue"),
    path("po/<int:po_pk>/fulfill/", views.po_fulfill, name="po_fulfill"),
    path("po/<int:po_pk>/cancel/", views.po_cancel, name="po_cancel"),
    path("po/<int:po_pk>/line-items/<int:li_pk>/eta/", views.po_li_eta, name="po_li_eta"),
    path("po/<int:po_pk>/line-items/<int:li_pk>/delivery/", views.po_li_delivery, name="po_li_delivery"),
    # Phase 4 — Stock & Delivery
    path("po/<int:po_pk>/documents/upload/", views.doc_upload, name="doc_upload"),
    path("po/<int:po_pk>/pod/upload/", views.pod_upload, name="pod_upload"),
    path("po/<int:po_pk>/stock/<int:li_pk>/update/", views.stock_update, name="stock_update"),
    # PHASE 5: Payment Requisition (NEW)
    path('payment-requisitions/', views.payment_requisition_list, name='payment_requisition_list'),
    path('payment-requisitions/create/', views.payment_requisition_create, name='payment_requisition_create'),
    path('payment-requisitions/<int:pk>/', views.payment_requisition_detail, name='payment_requisition_detail'),
    path('payment-requisitions/<int:pk>/submit/', views.payment_requisition_submit, name='payment_requisition_submit'),
    path('payment-requisitions/<int:pk>/approve/l2/', views.payment_requisition_approve_l2, name='payment_requisition_approve_l2'),
    path('payment-requisitions/<int:pk>/approve/l3/', views.payment_requisition_approve_l3, name='payment_requisition_approve_l3'),
    path('payment-requisitions/<int:pk>/reject/', views.payment_requisition_reject, name='payment_requisition_reject'),
    path('payment-requisitions/<int:pk>/pay/', views.payment_requisition_pay, name='payment_requisition_pay'),
    path('payment-requisitions/queue/l2/', views.payment_requisition_l2_queue, name='payment_requisition_l2_queue'),
    path('payment-requisitions/queue/l3/', views.payment_requisition_l3_queue, name='payment_requisition_l3_queue'),
]
