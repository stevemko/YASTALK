from datetime import timedelta

from django.contrib.auth import authenticate
from django.contrib.auth.models import update_last_login
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken

from .auth_serializers import RegisterSerializer, user_payload
from .models import LoginActivity, Profile

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    return forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR')


def log_attempt(request, email, user, success):
    LoginActivity.objects.create(
        user=user,
        email_attempted=email[:254],
        success=success,
        ip_address=client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:255],
    )


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'register'

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(user_payload(user), status=201)


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request):
        email = (request.data.get('email') or '').strip().lower()
        password = request.data.get('password') or ''
        if not email or not password:
            return Response({'error': 'Email and password are required.'}, status=400)

        # Lock the account for a while after repeated failures
        window = timezone.now() - timedelta(minutes=LOCKOUT_MINUTES)
        failures = LoginActivity.objects.filter(
            email_attempted=email, success=False, created_at__gte=window
        ).count()
        if failures >= MAX_FAILED_ATTEMPTS:
            return Response(
                {'error': f'Too many failed attempts. Try again in {LOCKOUT_MINUTES} minutes.'},
                status=429,
            )

        user = authenticate(request, username=email, password=password)
        if user is None:
            log_attempt(request, email, None, False)
            # Same message whether the email or the password was wrong
            return Response({'error': 'Invalid email or password.'}, status=401)

        update_last_login(None, user)
        log_attempt(request, email, user, True)
        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': user_payload(user),
        })


class LogoutView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get('refresh')
        if token:
            try:
                RefreshToken(token).blacklist()     # this refresh token can never be used again
            except Exception:
                pass
        return Response(status=204)


class MeView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(user_payload(request.user))

    def patch(self, request):
        user = request.user
        for field in ('first_name', 'last_name'):
            if field in request.data:
                setattr(user, field, str(request.data[field])[:60])
        user.save()
        if 'phone' in request.data:
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.phone = str(request.data['phone'])[:15]
            profile.save()
        return Response(user_payload(user))
        