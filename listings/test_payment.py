#!/usr/bin/env python3
"""
Test script for Chapa payment integration
Run this script to test payment functionality
"""

import requests
import json
import sys
import os
from datetime import datetime, timedelta

# Add your Django project root to Python path
sys.path.append('/path/to/your/django/project')

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alx_travel_app.settings')
import django
django.setup()

from django.contrib.auth import get_user_model
from listings.models import Listing, Booking, Payment
from listings.services import ChapaService
from decimal import Decimal

User = get_user_model()

class PaymentTestRunner:
    def __init__(self):
        self.base_url = "http://localhost:8000/api"
        self.access_token = None
        self.test_user = None
        self.test_listing = None
        self.test_booking = None

    def setup_test_data(self):
        """Create test data for payment testing"""
        print("Setting up test data...")
        
        # Create test user
        self.test_user, created = User.objects.get_or_create(
            email="testuser@example.com",
            defaults={
                'first_name': 'Test',
                'last_name': 'User',
                'phone_number': '+251911000000',
                'role': 'guest'
            }
        )
        if created:
            self.test_user.set_password('testpassword123')
            self.test_user.save()
            print(f"Created test user: {self.test_user.email}")
        
        # Create test host
        test_host, created = User.objects.get_or_create(
            email="testhost@example.com",
            defaults={
                'first_name': 'Test',
                'last_name': 'Host',
                'phone_number': '+251911000001',
                'role': 'host'
            }
        )
        if created:
            test_host.set_password('testpassword123')
            test_host.save()
            print(f"Created test host: {test_host.email}")
        
        # Create test listing
        self.test_listing, created = Listing.objects.get_or_create(
            name="Test Property for Payment",
            defaults={
                'host_id': test_host,
                'description': 'A beautiful test property for payment integration testing',
                'location': 'Addis Ababa, Ethiopia',
                'price_per_night': Decimal('100.00')
            }
        )
        if created:
            print(f"Created test listing: {self.test_listing.name}")
        
        # Create test booking
        start_date = datetime.now().date() + timedelta(days=30)
        end_date = start_date + timedelta(days=3)
        
        self.test_booking, created = Booking.objects.get_or_create(
            listing_id=self.test_listing,
            user_id=self.test_user,
            start_date=start_date,
            end_date=end_date,
            defaults={
                'total_price': Decimal('300.00'),
                'status': 'pending'
            }
        )
        if created:
            print(f"Created test booking: {self.test_booking.booking_id}")

    def login_user(self):
        """Login test user and get access token"""
        print("Logging in test user...")
        
        login_data = {
            'email': self.test_user.email,
            'password': 'testpassword123'
        }
        
        response = requests.post(f"{self.base_url}/auth/login/", json=login_data)
        
        if response.status_code == 200:
            self.access_token = response.json().get('access_token')
            print(f"Login successful. Token: {self.access_token[:20]}...")
            return True
        else:
            print(f"Login failed: {response.text}")
            return False

    def test_payment_initiation(self):
        """Test payment initiation via API"""
        print("\n" + "="*50)
        print("TESTING PAYMENT INITIATION")
        print("="*50)
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        payment_data = {
            'booking_id': str(self.test_booking.booking_id),
            'return_url': 'http://localhost:3000/booking-success'
        }
        
        response = requests.post(
            f"{self.base_url}/bookings/{self.test_booking.booking_id}/initiate_payment/",
            json=payment_data,
            headers=headers
        )
        
        print(f"Response Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 201:
            data = response.json()
            print(f"✅ Payment initiation successful!")
            print(f"Checkout URL: {data['checkout_url']}")
            print(f"Transaction ID: {data['payment']['transaction_id']}")
            return data
        else:
            print(f"❌ Payment initiation failed")
            return None

    def test_direct_service_call(self):
        """Test Chapa service directly"""
        print("\n" + "="*50)
        print("TESTING DIRECT CHAPA SERVICE CALL")
        print("="*50)
        
        chapa_service = ChapaService()
        result = chapa_service.initiate_payment(
            self.test_booking, 
            'http://localhost:3000/booking-success'
        )
        
        print(f"Service Result: {result}")
        
        if result['success']:
            print(f"✅ Direct service call successful!")
            print(f"Checkout URL: {result['checkout_url']}")
            print(f"Transaction ID: {result['transaction_id']}")
            
            # Test verification
            print("\nTesting payment verification...")
            verification = chapa_service.verify_payment(result['transaction_id'])
            print(f"Verification Result: {verification}")
            
            return result
        else:
            print(f"❌ Direct service call failed: {result['error']}")
            return None

    def test_payment_verification(self, transaction_id):
        """Test payment verification via API"""
        print("\n" + "="*50)
        print("TESTING PAYMENT VERIFICATION")
        print("="*50)
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.post(
            f"{self.base_url}/bookings/{self.test_booking.booking_id}/verify_payment/",
            headers=headers
        )
        
        print(f"Response Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Payment verification successful!")
            return True
        else:
            print("❌ Payment verification failed")
            return False

    def test_payment_status(self):
        """Test payment status retrieval"""
        print("\n" + "="*50)
        print("TESTING PAYMENT STATUS RETRIEVAL")
        print("="*50)
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f"{self.base_url}/bookings/{self.test_booking.booking_id}/payment_status/",
            headers=headers
        )
        
        print(f"Response Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Payment status retrieval successful!")
            return True
        else:
            print("❌ Payment status retrieval failed")
            return False

    def cleanup_test_data(self):
        """Clean up test data"""
        print("\n" + "="*50)
        print("CLEANING UP TEST DATA")
        print("="*50)
        
        # Delete payment if exists
        try:
            if hasattr(self.test_booking, 'payment'):
                self.test_booking.payment.delete()
                print("Deleted test payment")
        except:
            pass
        
        # Delete booking
        if self.test_booking:
            self.test_booking.delete()
            print("Deleted test booking")
        
        # Delete listing
        if self.test_listing:
            self.test_listing.delete()
            print("Deleted test listing")
        
        print("Cleanup completed")

    def run_tests(self):
        """Run all payment tests"""
        print("CHAPA PAYMENT INTEGRATION TEST SUITE")
        print("=" * 60)
        
        try:
            # Setup
            self.setup_test_data()
            
            if not self.login_user():
                print("❌ Cannot proceed without authentication")
                return
            
            # Test payment initiation via API
            payment_data = self.test_payment_initiation()
            
            # Test direct service call
            service_result = self.test_direct_service_call()
            
            # Test payment verification if we have a transaction
            if payment_data:
                transaction_id = payment_data['payment']['transaction_id']
                self.test_payment_verification(transaction_id)
            
            # Test payment status
            self.test_payment_status()
            
            print("\n" + "="*50)
            print("TEST SUMMARY")
            print("="*50)
            print("✅ Payment initiation test completed")
            print("✅ Direct service call test completed")
            print("✅ Payment verification test completed")
            print("✅ Payment status test completed")
            print("\nNOTE: For full testing, complete a payment on Chapa's")
            print("sandbox environment using the checkout URL provided above.")
            
        except Exception as e:
            print(f"❌ Test failed with error: {str(e)}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Cleanup
            cleanup = input("\nDo you want to clean up test data? (y/n): ")
            if cleanup.lower() == 'y':
                self.cleanup_test_data()


def main():
    """Main function to run payment tests"""
    print("Starting Chapa Payment Integration Tests...\n")
    
    # Check if Chapa credentials are set
    chapa_key = os.environ.get('CHAPA_SECRET_KEY')
    if not chapa_key or chapa_key == 'your-chapa-secret-key-here':
        print("❌ CHAPA_SECRET_KEY environment variable not set!")
        print("Please set your Chapa secret key in your environment variables.")
        print("export CHAPA_SECRET_KEY='your-actual-secret-key'")
        return
    
    # Run tests
    test_runner = PaymentTestRunner()
    test_runner.run_tests()


if __name__ == "__main__":
    main()