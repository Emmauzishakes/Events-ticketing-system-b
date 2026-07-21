from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
from core.models import Event

class Command(BaseCommand):
    help = 'Sends email reminders to creators 1 week and 1 day remaining to their event.'

    def handle(self, *args, **kwargs):
        today = timezone.localdate()
        
        target_date_7_days = today + timedelta(days=7)
        target_date_1_day = today + timedelta(days=1)

        # Filter events where the START DATE matches the target dates
        upcoming_events_week = Event.objects.filter(
            start_date__date=target_date_7_days, 
            is_active=False
        )
        
        upcoming_events_day = Event.objects.filter(
            start_date__date=target_date_1_day,
            is_active=False
        )

        # Send 1-Week Reminders
        for event in upcoming_events_week:
            creator_email = event.creator.email
            send_mail(
                subject=f'Action Required: Your Chizzi Event "{event.name}" is 1 Week Away!',
                message=f'Hello,\n\nYour broadcast "{event.name}" is scheduled for next week ({event.start_date.strftime("%B %d, %Y")}). Make sure your streaming setup is ready.\n\n- Chizzi Studio Team',
                from_email='no-reply@chizzi.com',
                recipient_list=[creator_email],
                fail_silently=True,
            )
            self.stdout.write(self.style.SUCCESS(f'Sent 1-week reminder for {event.name}'))

        # Send 1-Day Reminders
        for event in upcoming_events_day:
            creator_email = event.creator.email
            send_mail(
                subject=f'URGENT: Your Chizzi Event "{event.name}" is TOMORROW!',
                message=f'Hello,\n\nYour broadcast "{event.name}" is tomorrow! Please log in early to test your connection.\n\n- Chizzi Studio Team',
                from_email='no-reply@chizzi.com',
                recipient_list=[creator_email],
                fail_silently=True,
            )
            self.stdout.write(self.style.SUCCESS(f'Sent 1-day reminder for {event.name}'))