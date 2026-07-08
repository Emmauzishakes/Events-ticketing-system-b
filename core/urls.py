from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'events', views.EventViewSet)
# router.register(r'tickets', views.TicketViewSet)


urlpatterns = [
    path('', include(router.urls)),

    path('pay/', views.initiate_stk_push, name='initiate-stk-push'),
    path('mpesa/callback/', views.mpesa_callback, name='mpesa-callback'),

    path('payment-status/<str:checkout_request_id>/', views.check_payment_status, name='payment-status'),
    path('validate-ticket/<uuid:ticket_id>/', views.validate_ticket, name='validate-ticket'),
    path('verify-receipt/', views.verify_mpesa_receipt, name='verify_receipt'),

    path('admin/metrics/', views.admin_dashboard_metrics, name='admin-dashboard-metrics'),
    path('admin/attendees/', views.admin_attendees_list, name='admin-attendees-list'),
]