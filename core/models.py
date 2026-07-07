from django.db import models
from django.utils.text import slugify
import uuid

# Create your models here.

class Event(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    date = models.DateTimeField()
    slug = models.SlugField(max_length=255, unique=True, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    stream_link = models.URLField(blank=True, null=True, help_text="The hidden Live or stream URL")
    is_approved = models.BooleanField(default=False, help_text="Designates whether this event is visible to the public.")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        status = "🟢 LIVE" if self.is_active else "🔴 ENDED"
        return f"{status} - {self.name}"

class Ticket(models.Model):
    """The digital access token generated upon payment."""
    # This UUID becomes their secret URL parameter: yourdomain.com/watch/4932ba2d...
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='access_tokens')
    created_at = models.DateTimeField(auto_now_add=True)
    allowed_device_ids = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"Access Token - {self.id}"

PAYMENT_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('successful', 'Successful'),
    ('failed', 'Failed'),
]

class Payment(models.Model):
    # Payment links directly to the Event
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='payments')
    # A user only gets one access token per payment
    ticket = models.OneToOneField(Ticket, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone_number = models.CharField(max_length=20)

    mpesa_checkout_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    mpesa_receipt_number = models.CharField(max_length=100, blank=True, null=True)
    mpesa_payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.phone_number} - {self.mpesa_payment_status} - {self.amount}"