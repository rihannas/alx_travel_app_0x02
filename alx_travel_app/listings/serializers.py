from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User, Listing, Booking, Review, Conversation, Message


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone_number', 'role', 'password', 'password_confirm']

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            user = authenticate(request=self.context.get('request'),
                              username=email, password=password)
            if not user:
                raise serializers.ValidationError('Invalid email or password')
            attrs['user'] = user
        else:
            raise serializers.ValidationError('Must include email and password')
        
        return attrs


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['user_id', 'email', 'first_name', 'last_name', 'phone_number', 'role', 'created_at']
        read_only_fields = ['user_id', 'created_at']


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone_number']


class ListingSerializer(serializers.ModelSerializer):
    host_id = serializers.PrimaryKeyRelatedField(read_only=True)
    host_name = serializers.CharField(source='host_id.get_full_name', read_only=True)
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            'listing_id', 'host_id', 'host_name', 'name', 'description', 
            'location', 'price_per_night', 'created_at', 'updated_at',
            'average_rating', 'review_count'
        ]
        read_only_fields = ['listing_id', 'host_id', 'created_at', 'updated_at']

    def get_average_rating(self, obj):
        reviews = obj.reviews.all()
        if reviews:
            return round(sum(review.rating for review in reviews) / len(reviews), 1)
        return None

    def get_review_count(self, obj):
        return obj.reviews.count()

    def create(self, validated_data):
        validated_data['host_id'] = self.context['request'].user
        return super().create(validated_data)


class ListingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing
        fields = ['name', 'description', 'location', 'price_per_night']

    def create(self, validated_data):
        validated_data['host_id'] = self.context['request'].user
        return super().create(validated_data)


class BookingSerializer(serializers.ModelSerializer):
    user_id = serializers.PrimaryKeyRelatedField(read_only=True)
    user_name = serializers.CharField(source='user_id.get_full_name', read_only=True)
    listing_name = serializers.CharField(source='listing_id.name', read_only=True)
    listing_location = serializers.CharField(source='listing_id.location', read_only=True)
    host_name = serializers.CharField(source='listing_id.host_id.get_full_name', read_only=True)

    class Meta:
        model = Booking
        fields = [
            'booking_id', 'listing_id', 'listing_name', 'listing_location',
            'user_id', 'user_name', 'host_name', 'start_date', 'end_date',
            'total_price', 'status', 'created_at'
        ]
        read_only_fields = ['booking_id', 'user_id', 'total_price', 'created_at']

    def validate(self, attrs):
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        listing = attrs.get('listing_id')

        # Validate dates
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("End date must be after start date")

            # Check for overlapping bookings
            overlapping_bookings = Booking.objects.filter(
                listing_id=listing,
                status__in=['pending', 'confirmed']
            ).filter(
                start_date__lt=end_date,
                end_date__gt=start_date
            )

            if self.instance:
                overlapping_bookings = overlapping_bookings.exclude(pk=self.instance.pk)

            if overlapping_bookings.exists():
                raise serializers.ValidationError("Property is not available for selected dates")

        return attrs

    def create(self, validated_data):
        validated_data['user_id'] = self.context['request'].user
        
        # Calculate total price
        start_date = validated_data['start_date']
        end_date = validated_data['end_date']
        listing = validated_data['listing_id']
        nights = (end_date - start_date).days
        validated_data['total_price'] = nights * listing.price_per_night
        
        return super().create(validated_data)


class BookingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = ['listing_id', 'start_date', 'end_date']

    def validate(self, attrs):
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        listing = attrs.get('listing_id')

        # Validate dates
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("End date must be after start date")

            # Check for overlapping bookings
            overlapping_bookings = Booking.objects.filter(
                listing_id=listing,
                status__in=['pending', 'confirmed'],
                start_date__lt=end_date,
                end_date__gt=start_date
            )

            if overlapping_bookings.exists():
                raise serializers.ValidationError("Property is not available for selected dates")

        return attrs


class ReviewSerializer(serializers.ModelSerializer):
    user_id = serializers.PrimaryKeyRelatedField(read_only=True)
    user_name = serializers.CharField(source='user_id.get_full_name', read_only=True)
    listing_name = serializers.CharField(source='listing_id.name', read_only=True)

    class Meta:
        model = Review
        fields = [
            'review_id', 'listing_id', 'listing_name', 'user_id', 'user_name',
            'rating', 'comment', 'created_at'
        ]
        read_only_fields = ['review_id', 'user_id', 'created_at']

    def validate_rating(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value

    def validate(self, attrs):
        listing = attrs.get('listing_id')
        user = self.context['request'].user

        # Check if user has already reviewed this listing
        if Review.objects.filter(listing_id=listing, user_id=user).exists():
            raise serializers.ValidationError("You have already reviewed this listing")

        # Optional: Check if user has actually booked this listing
        has_booking = Booking.objects.filter(
            listing_id=listing,
            user_id=user,
            status='confirmed'
        ).exists()

        if not has_booking:
            raise serializers.ValidationError("You can only review listings you have booked")

        return attrs

    def create(self, validated_data):
        validated_data['user_id'] = self.context['request'].user
        return super().create(validated_data)


class ReviewCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ['listing_id', 'rating', 'comment']


class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.PrimaryKeyRelatedField(read_only=True)
    sender_name = serializers.CharField(source='sender.get_full_name', read_only=True)

    class Meta:
        model = Message
        fields = ['message_id', 'sender', 'sender_name', 'message_body', 'sent_at']
        read_only_fields = ['message_id', 'sender', 'sent_at']


class ConversationSerializer(serializers.ModelSerializer):
    participants = UserSerializer(many=True, read_only=True)
    messages = MessageSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ['conversation_id', 'participants', 'messages', 'last_message', 'created_at']
        read_only_fields = ['conversation_id', 'created_at']

    def get_last_message(self, obj):
        last_message = obj.messages.order_by('-sent_at').first()
        if last_message:
            return MessageSerializer(last_message).data
        return None


class ConversationCreateSerializer(serializers.Serializer):
    participant_email = serializers.EmailField()
    message_body = serializers.CharField(max_length=1000)

    def validate_participant_email(self, value):
        try:
            participant = User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist")
        return value