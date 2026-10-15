from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from rest_framework import serializers

from .models import Profile

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    first_name = serializers.CharField(max_length=60)
    last_name = serializers.CharField(max_length=60, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=15, required=False, allow_blank=True)

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(Q(username__iexact=value) | Q(email__iexact=value)).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return value

    def validate(self, attrs):
        # Django's validators: minimum length, common passwords, numeric-only, similarity to user data
        probe = User(username=attrs['email'], email=attrs['email'], first_name=attrs.get('first_name', ''))
        try:
            validate_password(attrs['password'], user=probe)
        except DjangoValidationError as e:
            raise serializers.ValidationError({'password': list(e.messages)})
        return attrs

    @transaction.atomic
    def create(self, data):
        user = User.objects.create_user(
            username=data['email'],
            email=data['email'],
            password=data['password'],          # hashed by Django, never stored as plain text
            first_name=data['first_name'],
            last_name=data.get('last_name', ''),
        )
        Profile.objects.create(user=user, phone=data.get('phone', ''))
        return user


def user_payload(user):
    profile = getattr(user, 'profile', None)
    return {
        'id': user.id,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'phone': profile.phone if profile else '',
        'date_joined': user.date_joined,
    }