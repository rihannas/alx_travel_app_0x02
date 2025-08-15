from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from alx_travel_app.listings.models import Listing, Booking, Review, Conversation, Message
from decimal import Decimal
from datetime import date, timedelta
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed the database with sample data for ALX Travel App'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=20,
            help='Number of users to create (default: 20)'
        )
        parser.add_argument(
            '--listings',
            type=int,
            default=30,
            help='Number of listings to create (default: 30)'
        )
        parser.add_argument(
            '--bookings',
            type=int,
            default=50,
            help='Number of bookings to create (default: 50)'
        )
        parser.add_argument(
            '--reviews',
            type=int,
            default=40,
            help='Number of reviews to create (default: 40)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before seeding'
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write(
                self.style.WARNING('Clearing existing data...')
            )
            self.clear_data()

        self.stdout.write(
            self.style.SUCCESS('Starting database seeding...')
        )

        # Create users
        users = self.create_users(options['users'])
        self.stdout.write(
            self.style.SUCCESS(f'Created {len(users)} users')
        )

        # Create listings
        listings = self.create_listings(users, options['listings'])
        self.stdout.write(
            self.style.SUCCESS(f'Created {len(listings)} listings')
        )

        # Create bookings
        bookings = self.create_bookings(users, listings, options['bookings'])
        self.stdout.write(
            self.style.SUCCESS(f'Created {len(bookings)} bookings')
        )

        # Create reviews
        reviews = self.create_reviews(users, listings, options['reviews'])
        self.stdout.write(
            self.style.SUCCESS(f'Created {len(reviews)} reviews')
        )

        # Create conversations
        conversations = self.create_conversations(users)
        self.stdout.write(
            self.style.SUCCESS(f'Created {len(conversations)} conversations')
        )

        self.stdout.write(
            self.style.SUCCESS('Database seeding completed successfully!')
        )

    def clear_data(self):
        """Clear existing data from all models"""
        Message.objects.all().delete()
        Conversation.objects.all().delete()
        Review.objects.all().delete()
        Booking.objects.all().delete()
        Listing.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()

    def create_users(self, count):
        """Create sample users"""
        users = []
        
        # Sample data
        first_names = [
            'John', 'Jane', 'Michael', 'Sarah', 'David', 'Lisa', 'Robert', 'Emily',
            'James', 'Jennifer', 'William', 'Jessica', 'Richard', 'Ashley', 'Charles',
            'Amanda', 'Thomas', 'Stephanie', 'Daniel', 'Nicole'
        ]
        
        last_names = [
            'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller',
            'Davis', 'Rodriguez', 'Martinez', 'Hernandez', 'Lopez', 'Gonzalez',
            'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin'
        ]
        
        roles = ['guest', 'host', 'guest', 'host', 'guest']  # More guests than hosts
        
        for i in range(count):
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            email = f"{first_name.lower()}.{last_name.lower()}{i}@example.com"
            
            user = User.objects.create_user(
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone_number=f"+1{random.randint(2000000000, 9999999999)}",
                role=random.choice(roles),
                password='password123'
            )
            users.append(user)
        
        return users

    def create_listings(self, users, count):
        """Create sample listings"""
        listings = []
        
        # Get host users
        hosts = [user for user in users if user.role == 'host']
        if not hosts:
            # Make some users hosts if none exist
            for user in users[:5]:
                user.role = 'host'
                user.save()
                hosts.append(user)
        
        # Sample listing data
        property_types = [
            'Cozy Apartment', 'Luxury Villa', 'Beach House', 'Mountain Cabin',
            'City Loft', 'Country Cottage', 'Modern Condo', 'Historic Home',
            'Penthouse Suite', 'Lakefront Lodge'
        ]
        
        locations = [
            'New York, NY', 'Los Angeles, CA', 'Chicago, IL', 'Houston, TX',
            'Phoenix, AZ', 'Philadelphia, PA', 'San Antonio, TX', 'San Diego, CA',
            'Dallas, TX', 'San Jose, CA', 'Austin, TX', 'Jacksonville, FL',
            'Fort Worth, TX', 'Columbus, OH', 'Charlotte, NC', 'San Francisco, CA',
            'Indianapolis, IN', 'Seattle, WA', 'Denver, CO', 'Boston, MA'
        ]
        
        descriptions = [
            "A beautiful and comfortable place to stay with modern amenities and great location.",
            "Perfect for families and groups looking for a memorable vacation experience.",
            "Luxury accommodation with stunning views and premium facilities.",
            "Cozy retreat ideal for couples and solo travelers seeking tranquility.",
            "Modern space with all the amenities you need for a perfect stay.",
            "Charming property with unique character and excellent hospitality.",
            "Spacious and well-appointed accommodation in a prime location.",
            "Elegant retreat offering comfort and convenience for discerning guests."
        ]
        
        for i in range(count):
            host = random.choice(hosts)
            property_type = random.choice(property_types)
            location = random.choice(locations)
            
            listing = Listing.objects.create(
                host_id=host,
                name=f"{property_type} in {location.split(',')[0]}",
                description=random.choice(descriptions),
                location=location,
                price_per_night=Decimal(str(random.randint(50, 500)))
            )
            listings.append(listing)
        
        return listings

    def create_bookings(self, users, listings, count):
        """Create sample bookings"""
        bookings = []
        
        # Get guest users
        guests = [user for user in users if user.role == 'guest']
        if not guests:
            guests = users[:10]  # Use first 10 users as guests if no guests exist
        
        statuses = ['pending', 'confirmed', 'canceled']
        status_weights = [0.2, 0.7, 0.1]  # Most bookings should be confirmed
        
        for i in range(count):
            guest = random.choice(guests)
            listing = random.choice(listings)
            
            # Generate random dates
            start_date = date.today() + timedelta(days=random.randint(-30, 60))
            end_date = start_date + timedelta(days=random.randint(1, 10))
            
            # Calculate total price
            nights = (end_date - start_date).days
            total_price = nights * listing.price_per_night
            
            # Check for overlapping bookings (simplified check)
            overlapping = Booking.objects.filter(
                listing_id=listing,
                start_date__lt=end_date,
                end_date__gt=start_date,
                status__in=['pending', 'confirmed']
            ).exists()
            
            if not overlapping:
                booking = Booking.objects.create(
                    listing_id=listing,
                    user_id=guest,
                    start_date=start_date,
                    end_date=end_date,
                    total_price=total_price,
                    status=random.choices(statuses, weights=status_weights)[0]
                )
                bookings.append(booking)
        
        return bookings

    def create_reviews(self, users, listings, count):
        """Create sample reviews"""
        reviews = []
        
        review_comments = [
            "Amazing place! Everything was perfect and the host was very helpful.",
            "Great location and beautiful property. Would definitely stay again!",
            "Clean, comfortable, and exactly as described. Highly recommended.",
            "Perfect for our family vacation. Kids loved it!",
            "Excellent value for money. Great amenities and friendly service.",
            "Beautiful views and peaceful atmosphere. Very relaxing stay.",
            "Modern and well-equipped. Everything we needed was provided.",
            "Fantastic experience! The property exceeded our expectations.",
            "Good location but could use some updates to the furnishing.",
            "Decent stay overall. Clean and comfortable with good communication.",
            "Outstanding hospitality! Made our trip truly memorable.",
            "Perfect getaway spot. Quiet, clean, and beautifully decorated."
        ]
        
        # Get users who have confirmed bookings
        confirmed_bookings = Booking.objects.filter(status='confirmed')
        
        created_count = 0
        for booking in confirmed_bookings:
            if created_count >= count:
                break
                
            # Only create review if one doesn't already exist
            if not Review.objects.filter(
                listing_id=booking.listing_id,
                user_id=booking.user_id
            ).exists():
                
                review = Review.objects.create(
                    listing_id=booking.listing_id,
                    user_id=booking.user_id,
                    rating=random.randint(3, 5),  # Mostly positive reviews
                    comment=random.choice(review_comments)
                )
                reviews.append(review)
                created_count += 1
        
        return reviews

    def create_conversations(self, users):
        """Create sample conversations"""
        conversations = []
        
        sample_messages = [
            "Hi! I'm interested in your property. Is it available for the dates I selected?",
            "Hello! Yes, it's available. I'd be happy to host you!",
            "Great! Can you tell me more about the local area?",
            "The location is perfect for exploring the city. There are great restaurants nearby.",
            "That sounds wonderful. I'll go ahead and book it.",
            "Excellent! Looking forward to hosting you. Let me know if you need anything.",
            "Thank you for the great stay! Everything was perfect.",
            "You were wonderful guests! Please come back anytime."
        ]
        
        # Create conversations between random users
        for i in range(min(10, len(users) // 2)):
            participants = random.sample(users, 2)
            
            conversation = Conversation.objects.create()
            conversation.participants.set(participants)
            
            # Add some messages to the conversation
            for j in range(random.randint(2, 6)):
                sender = random.choice(participants)
                message = Message.objects.create(
                    sender=sender,
                    conversation=conversation,
                    message_body=random.choice(sample_messages)
                )
            
            conversations.append(conversation)
        
        return conversations