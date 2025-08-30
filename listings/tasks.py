from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

@shared_task
def send_booking_email(customer_email, booking_details):
    """Send a booking confirmation email asynchronously."""
    subject = "Booking Confirmation"
    message = f"Dear customer,\n\nYour booking has been confirmed.\n\nDetails:\n{booking_details}"
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [customer_email]

    send_mail(subject, message, from_email, recipient_list)
