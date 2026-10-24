import logging
import threading
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import update_last_login
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core import signing
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from urllib.parse import quote
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from .auth_serializers import RegisterSerializer, is_email_verified, normalize_phone, user_payload
from .models import LoginActivity, Profile

logger = logging.getLogger(__name__)
User = get_user_model()

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


def _send_in_background(subject, body, to_email):
    """Send an email without making the request wait for the mail server."""
    def _send():
        try:
            send_mail(subject, body, None, [to_email])
        except Exception:
            logger.exception('Could not send email to a user')

    threading.Thread(target=_send, daemon=True).start()


VERIFY_SALT = 'yastalk-email-verify'


def send_verification_email(user):
    """Email a signed link. It stops working if the email changes or after 3 days."""
    token = signing.dumps({'uid': user.pk, 'email': user.email}, salt=VERIFY_SALT)
    link = f'{settings.FRONTEND_URL}/verify-email?token={quote(token, safe="")}'
    _send_in_background(
        'Confirm your YasTalk email',
        f'Hi {user.first_name or "there"},\n\n'
        f'Please confirm your email address so you can pay and recover your account '
        f'if you ever forget your password:\n{link}\n\n'
        f'This link works for 3 days. If you did not create a YasTalk account, ignore this email.',
        user.email,
    )


def _notify_password_changed(user):
    _send_in_background(
        'Your YasTalk password was changed',
        f'Hi {user.first_name or "there"},\n\n'
        f'The password on your YasTalk account was just changed. If this was you, no action '
        f'is needed.\n\nIf it was not you, reset your password now at '
        f'{settings.FRONTEND_URL}/forgot-password and contact us.',
        user.email,
    )


def _blacklist_all_sessions(user):
    for outstanding in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=outstanding)


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'register'

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        send_verification_email(user)
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

        # Find the account by email, whatever its username is (e.g. a superuser
        # created with createsuperuser has a username that is not the email).
        account = User.objects.filter(email__iexact=email).first()
        user = (
            authenticate(request, username=account.get_username(), password=password)
            if account
            else None
        )
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
    """Needs only the refresh token, so logout still works after the
    15-minute access token has expired."""
    permission_classes = [AllowAny]
    authentication_classes = []

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

        phone = None
        if 'phone' in request.data:
            raw = str(request.data['phone']).strip()
            phone = normalize_phone(raw) if raw else ''
            if phone is None:
                return Response(
                    {'phone': ['Enter a valid Kenyan number, e.g. 0712345678.']}, status=400
                )

        for field in ('first_name', 'last_name'):
            if field in request.data:
                setattr(user, field, str(request.data[field])[:60])
        user.save()

        if phone is not None:
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.phone = phone
            profile.save()
        return Response(user_payload(user))


class PasswordResetRequestView(APIView):
    """POST {email} -> emails a reset link. Always answers the same way."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    def post(self, request):
        email = (request.data.get('email') or '').strip().lower()
        user = User.objects.filter(email__iexact=email, is_active=True).first() if email else None
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            link = f'{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}'
            _send_in_background(
                'Reset your YasTalk password',
                f'Hi {user.first_name or "there"},\n\n'
                f'Use this link to set a new password (valid for 1 hour):\n{link}\n\n'
                f'If you did not ask for this, you can ignore this email.',
                user.email,
            )
        # Same answer whether or not the email has an account
        return Response({'detail': 'If that email has an account, a reset link has been sent.'})


class PasswordResetConfirmView(APIView):
    """POST {uid, token, password} -> sets the new password and logs out all sessions."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    def post(self, request):
        uid = request.data.get('uid') or ''
        token = request.data.get('token') or ''
        password = request.data.get('password') or ''

        try:
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            user = None

        if user is None or not default_token_generator.check_token(user, token):
            return Response({'error': 'This reset link is invalid or has expired.'}, status=400)

        try:
            validate_password(password, user=user)
        except DjangoValidationError as e:
            return Response({'password': list(e.messages)}, status=400)

        user.set_password(password)
        user.save()

        # Log out every existing session for this account
        _blacklist_all_sessions(user)
        _notify_password_changed(user)

        return Response({'detail': 'Password updated. You can now log in.'})


class VerifyEmailView(APIView):
    """POST {token} -> marks the email as verified. Safe to call twice."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'verify'

    def post(self, request):
        token = request.data.get('token') or ''
        try:
            data = signing.loads(token, salt=VERIFY_SALT, max_age=settings.EMAIL_VERIFY_MAX_AGE)
            user = User.objects.get(pk=data['uid'], is_active=True)
        except (signing.BadSignature, User.DoesNotExist, KeyError, TypeError, ValueError):
            return Response(
                {'error': 'This confirmation link is invalid or has expired.'}, status=400
            )
        if user.email.lower() != str(data.get('email', '')).lower():
            return Response(
                {'error': 'This confirmation link is invalid or has expired.'}, status=400
            )

        profile, _ = Profile.objects.get_or_create(user=user)
        if not profile.email_verified:
            profile.email_verified = True
            profile.save(update_fields=['email_verified'])
        return Response({'detail': 'Email confirmed. Thank you!', 'email_verified': True})


class ResendVerificationView(APIView):
    """POST (logged in) -> sends a fresh confirmation link."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'verify_resend'

    def post(self, request):
        if is_email_verified(request.user):
            return Response({'detail': 'Your email is already confirmed.', 'email_verified': True})
        send_verification_email(request.user)
        return Response({'detail': f'Confirmation link sent to {request.user.email}.'})


class ChangePasswordView(APIView):
    """POST {current_password, new_password} -> changes it and logs out other devices."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'change_password'

    def post(self, request):
        user = request.user
        current = request.data.get('current_password') or ''
        new = request.data.get('new_password') or ''

        if not user.check_password(current):
            return Response({'current_password': ['Your current password is not correct.']}, status=400)
        if new == current:
            return Response({'new_password': ['Choose a password different from your current one.']}, status=400)
        try:
            validate_password(new, user=user)
        except DjangoValidationError as e:
            return Response({'new_password': list(e.messages)}, status=400)

        user.set_password(new)
        user.save()

        # Every old session dies; this device gets a fresh one so you stay logged in.
        _blacklist_all_sessions(user)
        _notify_password_changed(user)
        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': user_payload(user),
            'detail': 'Password changed. Other devices have been logged out.',
        })
