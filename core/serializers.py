from rest_framework import serializers
from .models import Event, Ticket, Payment

class TicketSerializer(serializers.ModelSerializer):
    event_name = serializers.CharField(source='event.name', read_only=True)

    class Meta:
        model = Ticket
        fields = '__all__'
        read_only_fields = ['id', 'created_at']

class EventSerializer(serializers.ModelSerializer):
    tickets = TicketSerializer(many=True, read_only=True)

    class Meta:
        model = Event
        fields = '__all__'

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ['id', 'mpesa_checkout_id', 'mpesa_receipt_number', 'mpesa_payment_status', 'created_at', 'updated_at']