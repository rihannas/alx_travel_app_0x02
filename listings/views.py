# Create your views here.
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.decorators import action
from django.http import JsonResponse
from .models import Listing, Booking, Payment
from .serializers import (
    ListingSerializer, BookingSerializer, PaymentSerializer,
    PaymentInitiateSerializer, PaymentVerifySerializer
)
from .services import ChapaService
from .tasks import send_booking_email


import json
import logging

logger = logging.getLogger(__name__)


class ListingViewSet(viewsets.ModelViewSet):
    queryset = Listing.objects.all()
    serializer_class = ListingSerializer


class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        booking = serializer.save()
        # Trigger Celery task
        send_booking_email.delay(
            booking.customer.email,
            f"Booking ID: {booking.id}, Date: {booking.date}, Destination: {booking.destination}"
        )

    def get_queryset(self):
        """Filter bookings based on user role"""
        user = self.request.user
        if user.role == 'admin':
            return Booking.objects.all()
        elif user.role == 'host':
            return Booking.objects.filter(listing_id__host_id=user)
        else:  # guest
            return Booking.objects.filter(user_id=user)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def initiate_payment(self, request, pk=None):
        """
        Initiate payment for a booking using Chapa API
        """
        booking = get_object_or_404(Booking, pk=pk)
        
        # Check if user owns this booking
        if booking.user_id != request.user:
            return Response(
                {'error': 'You can only initiate payment for your own bookings'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if payment already exists
        if hasattr(booking, 'payment'):
            return Response(
                {
                    'error': 'Payment already exists for this booking',
                    'payment_status': booking.payment.status,
                    'checkout_url': booking.payment.chapa_checkout_url
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = PaymentInitiateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            return_url = serializer.validated_data['return_url']
            
            chapa_service = ChapaService()
            result = chapa_service.initiate_payment(booking, return_url)
            
            if result['success']:
                payment_serializer = PaymentSerializer(result['payment'])
                return Response({
                    'success': True,
                    'message': 'Payment initiated successfully',
                    'payment': payment_serializer.data,
                    'checkout_url': result['checkout_url']
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'success': False,
                    'error': result['error']
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def verify_payment(self, request, pk=None):
        """
        Verify payment status with Chapa API
        """
        booking = get_object_or_404(Booking, pk=pk)
        
        # Check if user owns this booking
        if booking.user_id != request.user:
            return Response(
                {'error': 'You can only verify payment for your own bookings'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if payment exists
        if not hasattr(booking, 'payment'):
            return Response(
                {'error': 'No payment found for this booking'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        payment = booking.payment
        chapa_service = ChapaService()
        
        # Verify payment with Chapa
        verification_result = chapa_service.verify_payment(payment.transaction_id)
        
        if verification_result['success']:
            # Update payment status
            chapa_service.update_payment_status(payment, verification_result)
            
            # Refresh payment data
            payment.refresh_from_db()
            payment_serializer = PaymentSerializer(payment)
            
            return Response({
                'success': True,
                'message': 'Payment verified successfully',
                'payment': payment_serializer.data,
                'verification_data': verification_result
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'error': verification_result['error']
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def payment_status(self, request, pk=None):
        """
        Get payment status for a booking
        """
        booking = get_object_or_404(Booking, pk=pk)
        
        # Check if user has access to this booking
        if booking.user_id != request.user and booking.listing_id.host_id != request.user:
            return Response(
                {'error': 'You do not have permission to view this payment'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if hasattr(booking, 'payment'):
            payment_serializer = PaymentSerializer(booking.payment)
            return Response({
                'success': True,
                'payment': payment_serializer.data
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'message': 'No payment found for this booking'
            }, status=status.HTTP_404_NOT_FOUND)


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter payments based on user role"""
        user = self.request.user
        if user.role == 'admin':
            return Payment.objects.all()
        elif user.role == 'host':
            return Payment.objects.filter(booking__listing_id__host_id=user)
        else:  # guest
            return Payment.objects.filter(booking__user_id=user)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def verify_by_transaction_id(self, request):
        """
        Verify payment by transaction ID
        """
        serializer = PaymentVerifySerializer(data=request.data)
        if serializer.is_valid():
            transaction_id = serializer.validated_data['transaction_id']
            
            try:
                payment = Payment.objects.get(transaction_id=transaction_id)
                
                # Check if user has access to this payment
                if (payment.booking.user_id != request.user and 
                    payment.booking.listing_id.host_id != request.user):
                    return Response(
                        {'error': 'You do not have permission to verify this payment'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                chapa_service = ChapaService()
                verification_result = chapa_service.verify_payment(transaction_id)
                
                if verification_result['success']:
                    chapa_service.update_payment_status(payment, verification_result)
                    payment.refresh_from_db()
                    
                    payment_serializer = PaymentSerializer(payment)
                    return Response({
                        'success': True,
                        'message': 'Payment verified successfully',
                        'payment': payment_serializer.data
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'success': False,
                        'error': verification_result['error']
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            except Payment.DoesNotExist:
                return Response(
                    {'error': 'Payment not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@method_decorator(csrf_exempt, name='dispatch')
class PaymentCallbackView(APIView):
    permission_classes = [AllowAny]  # Webhooks don't require auth

    def post(self, request, *args, **kwargs):
        try:
            callback_data = json.loads(request.body)
            transaction_id = callback_data.get('tx_ref')
            status = callback_data.get('status', '').lower()
            
            if transaction_id:
                try:
                    payment = Payment.objects.get(transaction_id=transaction_id)
                    status_mapping = {
                        'success': 'completed',
                        'failed': 'failed',
                        'pending': 'pending'
                    }
                    payment.status = status_mapping.get(status, 'pending')
                    payment.save()
                    
                    # Update booking status
                    if payment.status == 'completed':
                        payment.booking.status = 'confirmed'
                        payment.booking.save()
                        ChapaService().send_confirmation_email(payment.booking)
                    elif payment.status == 'failed':
                        payment.booking.status = 'canceled'
                        payment.booking.save()
                    
                    return JsonResponse({'success': True, 'message': 'Callback processed successfully'})
                
                except Payment.DoesNotExist:
                    return JsonResponse({'success': False, 'error': 'Payment not found'}, status=404)
            else:
                return JsonResponse({'success': False, 'error': 'Invalid callback data'}, status=400)

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            logger.error(f"Error processing callback: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Internal server error'}, status=500)