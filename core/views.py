import base64
from os import stat
import requests
import math
import io
from datetime import datetime
from django.db import transaction
from django.db.models import Sum, Count
from django.shortcuts import get_object_or_404
from django.http import FileResponse
from django.conf import settings
from .models import Event, Ticket, Payment, Voucher, generate_viewer_username
from .serializers import EventSerializer, TicketSerializer, PaymentSerializer
from rest_framework import viewsets, status
from rest_framework.permissions import BasePermission, SAFE_METHODS, IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, action, throttle_classes
from rest_framework.throttling import AnonRateThrottle

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

# Create your views here.

class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)

class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    lookup_field = 'slug'
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        return Event.objects.filter(is_approved=True).order_by('-created_at')
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def end_broadcast(self, request, slug=None):
        """Dedicated, secure endpoint to terminate an event."""
        event = self.get_object()
        event.is_active = False
        event.save()
        return Response({"message": f"Broadcast ended successfully."}, status=status.HTTP_200_OK)

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
    
    # error_msg = f"Failed to get M-Pesa token. Daraja Response: {r.text}"
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
    Frontend sends the Event ID they want to watch, their phone number, and an optional voucher.
    """
    event_id = request.data.get('event_id') 
    phone_number = request.data.get('phone_number')
    voucher_code = request.data.get('voucher_code')

    # 1. Only strictly require the Event ID upfront
    if not event_id:
        return Response({'error': 'Event ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

    event = get_object_or_404(Event, id=event_id)

    if not event.is_active:
        return Response({'error': 'This live event has ended.'}, status=status.HTTP_400_BAD_REQUEST)
    
    # 2. Calculate the final price FIRST
    final_price = int(event.price)
    voucher = None

    if voucher_code:
        try:
            voucher = Voucher.objects.get(code=voucher_code.strip().upper(), event=event, is_active=True)
            if voucher.has_slots_available:
                discount_amount = (final_price * voucher.discount_percentage) / 100
                final_price = max(0, math.ceil(final_price - discount_amount))
            else:
                return Response({"error": "This voucher has no remaining slots."}, status=status.HTTP_400_BAD_REQUEST)
        except Voucher.DoesNotExist:
            return Response({"error": "Invalid voucher code."}, status=status.HTTP_400_BAD_REQUEST)

    # 3. NOW validate the phone number ONLY if they actually need to pay
    if final_price > 0:
        if not phone_number:
            return Response({'error': 'Event ID and phone number are required.'}, status=status.HTTP_400_BAD_REQUEST)
        phone_number = format_phone_number(phone_number)
    else:
        # Assign a dummy value so the Payment model doesn't crash on null
        phone_number = "FREE-TICKET"

    # 4. Free Ticket Routing (100% Discount)
    if final_price == 0:
        with transaction.atomic():
            if voucher:
                # Lock the row to prevent race conditions
                voucher = Voucher.objects.select_for_update().get(id=voucher.id)
                voucher.slots_used += 1
                voucher.save()
            
            # Generate the digital access token instantly
            new_token = Ticket.objects.create(event=event)
            
            # Record a successful free payment
            Payment.objects.create(
                event=event,
                amount=0,
                phone_number=phone_number,
                mpesa_payment_status='successful',
                mpesa_receipt_number='FREE-VOUCHER',
                ticket=new_token
            )
            
        return Response({
            "message": "Free ticket generated successfully!",
            "is_free": True,
            "access_code": new_token.access_code
        }, status=status.HTTP_201_CREATED)

    # 5. Standard Paid Ticket Routing (M-Pesa STK Push)
    payment = Payment.objects.create(
        event=event,
        amount=final_price,
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
        "Amount": final_price, 
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
                "payment_id": payment.id,
                "is_free": False
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

# def get_client_ip(request):
#     """Helper function to get the real IP address from the request."""
#     x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
#     if x_forwarded_for:
#         ip = x_forwarded_for.split(',')[0].strip()
#     else:
#         ip = request.META.get('REMOTE_ADDR')
#     return ip

@api_view(['GET'])
def validate_ticket(request, access_code):
    """Frontend calls this when a user tries to load the stream page."""
    device_id = request.headers.get('X-Device-ID')

    if not device_id:
        return Response({"error": "Device ID is missing from request."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        ticket = Ticket.objects.get(access_code=access_code)
        if not ticket.username:
            ticket.username = generate_viewer_username()
            ticket.save()
    except Ticket.DoesNotExist:
        return Response({"error": "Invalid access token."}, status=status.HTTP_404_NOT_FOUND)

    if not ticket.event.is_active:
        return Response({"error": "This live event has ended."}, status=status.HTTP_403_FORBIDDEN)
    
    if not ticket.event.is_active:
        return Response({"error": "This live event has ended."}, status=status.HTTP_403_FORBIDDEN)
    
    MAX_DEVICES = 2
    # client_ip = get_client_ip(request)

    if device_id not in ticket.allowed_device_ids:
        if len(ticket.allowed_device_ids) >= MAX_DEVICES:
            return Response({
                "error": f"Device limit reached. This link is already in use on {MAX_DEVICES} devices."
            }, status=status.HTTP_403_FORBIDDEN)
        
        ticket.allowed_device_ids.append(device_id)
        ticket.save()

    return Response({
        "message": "Access granted",
        "event_name": ticket.event.name,
        "event_slug": ticket.event.slug,
        "username": ticket.username
    }, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_dashboard_metrics(request):
    """Returns platform-wide totals and the list of events for the dashboard."""
    # 1. Calculate Global Totals
    successful_payments = Payment.objects.filter(mpesa_payment_status='successful')
    total_revenue = successful_payments.aggregate(Sum('amount'))['amount__sum'] or 0
    total_tickets = Ticket.objects.count()
    active_streams = Event.objects.filter(is_active=True).count()

    # 2. Fetch all events with their individual performance
    events_data = []
    events = Event.objects.all().order_by('-created_at')
    
    for event in events:
        event_payments = successful_payments.filter(event=event)
        event_revenue = event_payments.aggregate(Sum('amount'))['amount__sum'] or 0
        event_tickets = Ticket.objects.filter(event=event).count()
        
        events_data.append({
            "id": event.id,
            "name": event.name,
            "slug": event.slug,
            "price": event.price,
            "is_active": event.is_active,
            "created_at": event.created_at,
            "revenue": event_revenue,
            "tickets_sold": event_tickets,
        })

    return Response({
        "metrics": {
            "total_revenue": total_revenue,
            "total_tickets": total_tickets,
            "active_streams": active_streams
        },
        "events": events_data
    }, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_attendees_list(request):
    """Returns a list of all successful buyers for the Attendees tab."""
    payments = Payment.objects.filter(mpesa_payment_status='successful').select_related('event').order_by('-id')
    
    attendees = [{
        "id": p.id,
        "phone_number": p.phone_number,
        "event_name": p.event.name,
        "amount": p.amount,
        "receipt": p.mpesa_receipt_number,
        "date": p.ticket.created_at if p.ticket else None
    } for p in payments]

    return Response(attendees, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
def verify_mpesa_receipt(request):
    """Allows users to retrieve their watch link using their M-Pesa receipt and phone Number."""
    receipt = request.data.get('receipt_number')
    phone = request.data.get('phone_number')

    if not receipt or not phone:
        return Response({"error": "Both receipt number and phone number are required."}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        receipt = receipt.strip().upper()
        phone = format_phone_number(phone)
        payment = Payment.objects.get(mpesa_receipt_number=receipt, phone_number=phone, mpesa_payment_status='successful')
        if not hasattr(payment, 'ticket') or not payment.ticket:
            return Response(
                {"error": "Payment received, but ticket is still generating. Please try again in 30 seconds."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response({
            "message": "Ticket retrieved successfully",
            "ticket_id": str(payment.ticket.id),
            "event_name": payment.event.name
        }, status=status.HTTP_200_OK)
    except Payment.DoesNotExist:
        return Response({"error": "Invalid details. The receipt and phone number combination was not found."}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([AllowAny])
def track_stream_view(request, slug):
    """
    Silent endpoint triggered when a viewer successfully connects to the WebRTC stream.
    Useful for tracking shared links and total shadow viewers.
    """
    try:
        event = Event.objects.get(slug=slug)
        # Assuming you add a 'total_views' IntegerField to your Event model later
        # event.total_views += 1 
        # event.save()
        
        # For now, we will just print it to the Django terminal to prove it works
        print(f"📈 ANALYTICS: New viewer joined '{event.name}'. Device IP: {request.META.get('REMOTE_ADDR')}")
        
        return Response({"status": "tracked"}, status=200)
    except Event.DoesNotExist:
        return Response({"error": "Event not found"}, status=404)
    
@api_view(['POST'])
@permission_classes([AllowAny])
def apply_voucher(request):
    event_slug = request.data.get('event_slug')
    voucher_code = request.data.get('code', '').strip().upper()

    try:
        event = Event.objects.get(slug=event_slug)
        voucher = Voucher.objects.get(code=voucher_code, event=event, is_active=True)

        if not voucher.has_slots_available:
            return Response({"error": "This voucher code is fully exhausted."}, status=status.HTTP_400_BAD_REQUEST)
        
        original_price = event.price
        discount_amount = (original_price * voucher.discount_percentage) / 100
        final_price = max(0, math.ceil(original_price - discount_amount))

        return Response({
            "valid": True,
            "code": voucher.code,
            "discount_percentage": voucher.discount_percentage,
            "discount_amount": discount_amount,
            "final_price": final_price,
            "is_free": final_price == 0
        }, status=status.HTTP_200_OK)
    
    except Event.DoesNotExist:
        return Response({"error": "Event not found."}, status=status.HTTP_404_NOT_FOUND)
    except Voucher.DoesNotExist:
        return Response({"error": "Invalid or expired voucher code."}, status=status.HTTP_400_BAD_REQUEST)
    
@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def admin_event_vouchers(request, event_id):
    """Admin endpoint to list and create vouchers for a specific event."""
    from .models import Event, Voucher
    
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return Response({"error": "Event not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        vouchers = Voucher.objects.filter(event=event).order_by('-created_at')
        data = [{
            "id": v.id,
            "code": v.code,
            "discount_percentage": v.discount_percentage,
            "max_slots": v.max_slots,
            "slots_used": v.slots_used,
            "is_active": v.is_active,
            "created_at": v.created_at
        } for v in vouchers]
        return Response(data, status=status.HTTP_200_OK)

    elif request.method == 'POST':
        discount = int(request.data.get('discount_percentage', 0))
        slots = int(request.data.get('max_slots', 0))
        custom_code = request.data.get('code', '').strip().upper()

        if discount < 1 or discount > 100:
            return Response({"error": "Discount must be between 1 and 100%"}, status=status.HTTP_400_BAD_REQUEST)
        if slots < 1:
            return Response({"error": "Max slots must be at least 1."}, status=status.HTTP_400_BAD_REQUEST)

        voucher = Voucher(event=event, discount_percentage=discount, max_slots=slots)
        
        if custom_code:
            if Voucher.objects.filter(code=custom_code).exists():
                return Response({"error": "This specific voucher code is already in use."}, status=status.HTTP_400_BAD_REQUEST)
            voucher.code = custom_code
            
        voucher.save()
        
        return Response({
            "message": "Voucher created successfully", 
            "voucher": {
                "id": voucher.id,
                "code": voucher.code,
                "discount_percentage": voucher.discount_percentage,
                "max_slots": voucher.max_slots,
                "slots_used": voucher.slots_used,
                "is_active": voucher.is_active
            }
        }, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([IsAdminUser])
def export_event_receipt_pdf(request, slug):
    """Generates secure, printable financial audit statement/receipt for a completed broadcast event."""
    event = get_object_or_404(Event, slug=slug)

    successful_payments = Payment.objects.filter(event=event, mpesa_payment_status='successful')
    total_revenue = successful_payments.aggregate(Sum('amount'))['amount__sum'] or 0
    total_tickets = Ticket.objects.filter(event=event).count()

    # Create an in-memory byte buffer pipeline for the file stream
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40
    )

    styles = getSampleStyleSheet()
    story = []

    # Custom Typography Styling Palette
    title_style = ParagraphStyle(
        'DocTitle',  parent=styles['Heading1'],
        fontSize=24, leading=14, textColor=colors.HexColor('#64748B'),
        spaceAfter=6
    )
    meta_style = ParagraphStyle(
        'DocMeta', parent=styles['Normal'],
        fontSize=10, leading=14, textColor=colors.HexColor('#64748B'),
        spaceAfter=20
    )
    th_style = ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=10, leading=12, textColor=colors.HexColor('#FFFFFF'))
    td_style = ParagraphStyle('TD', fontName='Helvetica', fontSize=9, leading=11, textColor=colors.HexColor('#1E293B'))

    # Document Header Elements
    story.append(Paragraph("CHIZZI STREAMING PLATFORM", title_style))
    story.append(Paragraph(f"Official Financial Audit Statement — Performance Record", meta_style))
    story.append(Spacer(1, 15))

    # Master Breakdown Grid Data
    summary_data = [
        [Paragraph("Metric Description", th_style), Paragraph("Value", th_style)],
        [Paragraph("Event Name / Title", td_style), Paragraph(event.name, td_style)],
        [Paragraph("Database Reference ID", td_style), Paragraph(str(event.id), td_style)],
        [Paragraph("Target Base Ticket Cost", td_style), Paragraph(f"KES {event.price}", td_style)],
        [Paragraph("Total System Passes Generated", td_style), Paragraph(str(total_tickets), td_style)],
        [Paragraph("Total Gross Volume Handled", td_style), Paragraph(f"KES {total_revenue:,.2f}", fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#16A34A'))],
    ]

    summary_table = Table(summary_data, colWidths=[250, 250])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (1,0), colors.HexColor('#0F172A')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')])
    ]))
    
    story.append(summary_table)
    story.append(Spacer(1, 30))

    # Generate File Document Structure
    doc.build(story)
    buffer.seek(0)

    # Return download headers directly to trigger native browser save prompts
    filename = f"Receipt-{event.slug}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename, content_type='application/pdf')