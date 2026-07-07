# from django.db import models
# from django.contrib.auth.models import User

# class CreatorApplication(models.Model):
#     STATUS_CHOICES = [
#         ('PENDING', 'Pending Review'),
#         ('APPROVED', 'Approved'),
#         ('REJECTED', 'Rejected'),
#     ]

#     user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='creator_profile')
    
#     # --- Professional Branding ---
#     brand_name = models.CharField(max_length=150, unique=True)
#     description = models.TextField(help_text="Details about the intended streaming content.")
#     website_url = models.URLField(blank=True, null=True)
    
#     # --- Strict Verification Parameters ---
#     phone_number = models.CharField(max_length=15, help_text="M-Pesa registered number for payouts")
#     national_id_passport = models.CharField(max_length=50, help_text="Legal ID/Passport for validation")
    
#     # --- Administration Status ---
#     status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
#     rejection_reason = models.TextField(blank=True, null=True)
    
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     def __str__(self):
#         return f"{self.brand_name} — {self.get_status_display()}"