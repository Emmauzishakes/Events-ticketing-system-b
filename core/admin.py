from django.contrib import admin
from .models import Event, Ticket, Payment

# Register your models here.
@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'is_approved', 'is_active', 'created_at', 'price')
    list_filter = ('is_approved', 'created_at', 'is_active')
    list_editable = ('is_approved', 'is_active')
    search_fields = ('name', 'description')
    ordering = ('-created_at',)

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    readonly_fields = ('id', 'created_at')
    list_display = ('id', 'event', 'created_at')
    list_filter = ('event', 'created_at')
    search_fields = ('id', 'event__name', )
    ordering = ('-created_at',)

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    # This makes debugging M-Pesa failures a breeze
    list_display = ('phone_number', 'event', 'amount', 'mpesa_payment_status', 'mpesa_receipt_number', 'created_at')
    list_filter = ('mpesa_payment_status', 'event', 'created_at')
    search_fields = ('phone_number', 'mpesa_receipt_number', 'mpesa_checkout_id')
    readonly_fields = ('mpesa_checkout_id', 'mpesa_receipt_number', 'created_at', 'updated_at')
    ordering = ('-created_at',)