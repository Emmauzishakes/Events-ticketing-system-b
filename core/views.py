import base64
import requests
from datetime import datetime
from django.shortcuts import get_object_or_404
from django.conf import settings
from .models import Event, Ticket, Payment
from .serializers import EventSerializer, TicketSerializer, PaymentSerializer
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import api_view

# Create your views here.

class EventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer

class TicketViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer

def get_mpesa_access_token():
    consumer_key = settings.MPESA_CONSUMER_KEY
    consumer_secret = settings.MPESA_CONSUMER_SECRET
    # print(f"--- DEBUG: Consumer Key is: {consumer_key} ---")
    # print(f"--- DEBUG: Consumer Secret is: {consumer_secret} ---")
    api_URL = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"  # Change to production URL in production

    r = requests.get(api_URL, auth=(consumer_key, consumer_secret))

    if r.status_code == 200:
        access_token = r.json()['access_token']
        return access_token
    
    error_msg = f"Failed to get M-Pesa token. Daraja Response: {r.text}"
    # print(f"--- DEBUG ERROR: {error_msg} ---")
    raise Exception("Failed to get M-Pesa access token")

def format_phone_number(phone):
    """Formats phone number to the required 254XXXXXXXXX format."""
    phone = phone.strip()
    if phone.startswith('0'):
        return f"254{phone[1:]}"
    if phone.startswith('+254'):
        return phone[1:]
    if phone.startswith('7') or phone.startswith('1'):
        return f"254{phone}"
    return phone

@api_view(['POST'])
def initiate_stk_push(request):
    """
    Frontend sends the Event ID they want to watch, and their phone number.
    """
    event_id = request.data.get('event_id') 
    phone_number = request.data.get('phone_number')

    if not event_id or not phone_number:
        return Response({'error': 'Event ID and phone number are required.'}, status=status.HTTP_400_BAD_REQUEST)

    event = get_object_or_404(Event, id=event_id)

    # 1. Stop payments if the show is over
    if not event.is_active:
        return Response({'error': 'This live event has ended.'}, status=status.HTTP_400_BAD_REQUEST)

    phone_number = format_phone_number(phone_number)
    amount = int(event.price)

    # 2. Create the pending Payment
    payment = Payment.objects.create(
        event=event,
        amount=amount,
        phone_number=phone_number,
        mpesa_payment_status='pending'
    )

    access_token = get_mpesa_access_token()
    api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    shortcode = settings.MPESA_SHORTCODE
    passkey = settings.MPESA_PASSKEY
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

    password_str = f"{shortcode}{passkey}{timestamp}"
    password = base64.b64encode(password_str.encode('utf-8')).decode('utf-8')

    callback_url = settings.MPESA_CALLBACK_URL

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone_number,
        "PartyB": shortcode,
        "PhoneNumber": phone_number,
        "CallBackURL": callback_url,
        "AccountReference": "Live Stream",
        "TransactionDesc": f"Access for {event.name}"
    }

    try:
        response = requests.post(api_url, json=payload, headers=headers)
        response_data = response.json()

        if response.status_code == 200 and response_data.get('ResponseCode') == '0':
            payment.mpesa_checkout_id = response_data['CheckoutRequestID']
            payment.save()

            return Response({
                "message": 'STK Push initiated. Check your phone.',
                "checkout_request_id": payment.mpesa_checkout_id,
                "payment_id": payment.id
            }, status=status.HTTP_200_OK)
        else:
            payment.mpesa_payment_status = 'failed'
            payment.save()
            return Response({'error': 'Failed to initiate STK Push', 'details': response_data}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        payment.mpesa_payment_status = 'failed'
        payment.save()
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def mpesa_callback(request):
    """
    Safaricom hits this URL. If successful, we generate the digital access token.
    """
    callback_data = request.data.get('Body', {}).get('stkCallback', {})
    checkout_request_id = callback_data.get('CheckoutRequestID')
    result_code = callback_data.get('ResultCode')

    if not checkout_request_id:
        return Response({'error': 'Invalid payload'}, status=status.HTTP_400_BAD_REQUEST)

    payment = get_object_or_404(Payment, mpesa_checkout_id=checkout_request_id)

    if str(result_code) == '0':
        metadata = callback_data.get('CallbackMetadata', {}).get('Item', [])
        receipt_number = next((item['Value'] for item in metadata if item['Name'] == 'MpesaReceiptNumber'), None)

        payment.mpesa_payment_status = 'successful'
        payment.mpesa_receipt_number = receipt_number
        
        # 3. SUCCESS -> Generate the digital access token
        new_token = Ticket.objects.create(event=payment.event)
        
        payment.ticket = new_token
        payment.save()

    else:
        payment.mpesa_payment_status = 'failed'
        payment.save()
        
    return Response({"ResultCode": 0, "ResultDesc": "Accepted"}, status=status.HTTP_200_OK)

@api_view(['GET'])
def check_payment_status(request, checkout_request_id):
    """Frontend polls this to see if the callback has arrived yet."""
    payment = get_object_or_404(Payment, mpesa_checkout_id=checkout_request_id)
    response_data = { "status": payment.mpesa_payment_status }

    if payment.mpesa_payment_status == 'successful' and payment.ticket:
        response_data['ticket_id'] = str(payment.ticket.id)

    return Response(response_data, status=status.HTTP_200_OK)

@api_view(['GET'])
def validate_ticket(request, ticket_id):
    """Frontend calls this when a user tries to load the stream page."""
    try:
        ticket = Ticket.objects.get(id=ticket_id)
    except Ticket.DoesNotExist:
        return Response({"error": "Invalid access token."}, status=status.HTTP_404_NOT_FOUND)

    if not ticket.event.is_active:
        return Response({"error": "This live event has ended."}, status=status.HTTP_403_FORBIDDEN)

    return Response({
        "message": "Access granted",
        "event_name": ticket.event.name,
        "stream_link": ticket.event.stream_link
    }, status=status.HTTP_200_OK)