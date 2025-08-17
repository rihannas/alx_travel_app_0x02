import requests
import uuid
from django.conf import settings
from django.core.mail import send_mail
from .models import Payment, Booking
import logging

logger = logging.getLogger(__name__)

class ChapaService:
    BASE_URL = "https://api.chapa.co/v1"
    
    def __init__(self):
        self.secret_key = settings.CHAPA_SECRET_KEY
        self.headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json'
        }

    def initiate_payment(self, booking, return_url):
        """
        Initiate payment with Chapa API
        """
        try:
            # Generate a unique transaction reference
            tx_ref = f"booking_{booking.booking_id}_{uuid.uuid4().hex[:8]}"
            
            payload = {
                "amount": str(booking.total_price),
                "currency": "ETB",
                "email": booking.user_id.email,
                "first_name": booking.user_id.first_name,
                "last_name": booking.user_id.last_name,
                "phone_number": booking.user_id.phone_number or "",
                "tx_ref": tx_ref,
                "callback_url": f"{return_url}/payment/callback/",
                "return_url": return_url,
                "description": f"Payment for booking at {booking.listing_id.name}",
                "meta": {
                    "booking_id": str(booking.booking_id),
                    "listing_name": booking.listing_id.name
                }
            }

            response = requests.post(
                f"{self.BASE_URL}/transaction/initialize",
                json=payload,
                headers=self.headers,
                timeout=30
            )
            
            logger.info(f"Chapa API response status: {response.status_code}")
            logger.info(f"Chapa API response: {response.text}")

            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    # Create payment record
                    payment = Payment.objects.create(
                        booking=booking,
                        transaction_id=tx_ref,
                        chapa_checkout_url=data['data']['checkout_url'],
                        amount=booking.total_price,
                        chapa_reference=data['data'].get('reference'),
                        status='pending'
                    )
                    return {
                        'success': True,
                        'payment': payment,
                        'checkout_url': data['data']['checkout_url'],
                        'transaction_id': tx_ref
                    }
                else:
                    return {
                        'success': False,
                        'error': data.get('message', 'Payment initialization failed')
                    }
            else:
                return {
                    'success': False,
                    'error': f'API request failed with status {response.status_code}'
                }

        except requests.RequestException as e:
            logger.error(f"Chapa API request error: {str(e)}")
            return {
                'success': False,
                'error': f'Network error: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Payment initiation error: {str(e)}")
            return {
                'success': False,
                'error': f'Internal error: {str(e)}'
            }

    def verify_payment(self, transaction_id):
        """
        Verify payment status with Chapa API
        """
        try:
            response = requests.get(
                f"{self.BASE_URL}/transaction/verify/{transaction_id}",
                headers=self.headers,
                timeout=30
            )

            logger.info(f"Chapa verification response status: {response.status_code}")
            logger.info(f"Chapa verification response: {response.text}")

            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    payment_data = data.get('data', {})
                    status = payment_data.get('status', '').lower()
                    
                    # Map Chapa status to our status
                    status_mapping = {
                        'success': 'completed',
                        'failed': 'failed',
                        'pending': 'pending'
                    }
                    
                    return {
                        'success': True,
                        'status': status_mapping.get(status, 'pending'),
                        'amount': payment_data.get('amount'),
                        'reference': payment_data.get('reference'),
                        'raw_data': payment_data
                    }
                else:
                    return {
                        'success': False,
                        'error': data.get('message', 'Verification failed')
                    }
            else:
                return {
                    'success': False,
                    'error': f'API request failed with status {response.status_code}'
                }

        except requests.RequestException as e:
            logger.error(f"Chapa verification request error: {str(e)}")
            return {
                'success': False,
                'error': f'Network error: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Payment verification error: {str(e)}")
            return {
                'success': False,
                'error': f'Internal error: {str(e)}'
            }

    def update_payment_status(self, payment, verification_result):
        """
        Update payment status based on verification result
        """
        try:
            if verification_result['success']:
                payment.status = verification_result['status']
                payment.save()
                
                # Update booking status if payment is completed
                if payment.status == 'completed':
                    payment.booking.status = 'confirmed'
                    payment.booking.save()
                    
                    # Send confirmation email (this should be moved to Celery task)
                    self.send_confirmation_email(payment.booking)
                    
                elif payment.status == 'failed':
                    payment.booking.status = 'canceled'
                    payment.booking.save()
                
                return True
            else:
                logger.error(f"Payment verification failed: {verification_result['error']}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating payment status: {str(e)}")
            return False

    def send_confirmation_email(self, booking):
        """
        Send booking confirmation email
        """
        try:
            subject = f"Booking Confirmation - {booking.listing_id.name}"
            message = f"""
            Dear {booking.user_id.first_name},
            
            Your booking has been confirmed!
            
            Booking Details:
            - Property: {booking.listing_id.name}
            - Location: {booking.listing_id.location}
            - Check-in: {booking.start_date}
            - Check-out: {booking.end_date}
            - Total Price: ETB {booking.total_price}
            
            Thank you for choosing our service!
            
            Best regards,
            ALX Travel Team
            """
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [booking.user_id.email],
                fail_silently=False,
            )
            
            logger.info(f"Confirmation email sent to {booking.user_id.email}")
            
        except Exception as e:
            logger.error(f"Error sending confirmation email: {str(e)}")

# Celery task for sending emails (optional - requires Celery setup)
# from celery import shared_task

# @shared_task
# def send_booking_confirmation_email(booking_id):
#     """
#     Celery task to send booking confirmation email
#     """
#     try:
#         booking = Booking.objects.get(booking_id=booking_id)
#         chapa_service = ChapaService()
#         chapa_service.send_confirmation_email(booking)
#     except Booking.DoesNotExist:
#         logger.error(f"Booking {booking_id} not found")
#     except Exception as e:
#         logger.error(f"Error in Celery email task: {str(e)}")