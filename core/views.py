import logging
import threading

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from rest_framework import viewsets, mixins, generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import Language, Service, TeamMember, Testimonial, ContactMessage, NewsletterSubscriber

logger = logging.getLogger(__name__)


def _email_enquiry(message):
    """Forward a website enquiry to the team inbox without slowing the request."""
    def _send():
        try:
            subject = message.subject or f'New enquiry from {message.name}'
            body = (
                f'Name: {message.name}\n'
                f'Email: {message.email}\n'
                f'Subject: {message.subject or "(none)"}\n\n'
                f'{message.message}\n\n'
                f'— Sent from the YasTalk website'
            )
            EmailMessage(
                subject=f'[YasTalk] {subject}',
                body=body,
                to=[settings.CONTACT_EMAIL],
                reply_to=[message.email],
            ).send(fail_silently=True)
        except Exception:
            logger.exception('Could not forward enquiry %s', message.pk)

    threading.Thread(target=_send, daemon=True).start()
from .serializers import (
    LanguageSerializer,
    ServiceSerializer,
    TeamMemberSerializer,
    TestimonialSerializer,
    ContactMessageSerializer,
    NewsletterSubscriberSerializer,
)


class LanguageViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer
    permission_classes = [AllowAny]


class ServiceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Service.objects.filter(is_published=True)
    serializer_class = ServiceSerializer
    permission_classes = [AllowAny]


class TeamMemberViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = TeamMember.objects.all()
    serializer_class = TeamMemberSerializer
    permission_classes = [AllowAny]


class TestimonialViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Testimonial.objects.filter(is_published=True)
    serializer_class = TestimonialSerializer
    permission_classes = [AllowAny]


class ContactMessageCreateView(generics.CreateAPIView):
    """POST /api/contact/ — open to everyone, no account needed.

    Guests fill in their own name and email; for a logged-in sender those two
    fields are taken from the account so the enquiry cannot be sent under
    someone else's identity.
    """
    queryset = ContactMessage.objects.all()
    serializer_class = ContactMessageSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'contact'

    def create(self, request, *args, **kwargs):
        user = request.user if request.user.is_authenticated else None
        data = request.data.copy()
        if user:
            data['name'] = user.get_full_name() or user.email
            data['email'] = user.email
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        message = serializer.save(user=user)
        _email_enquiry(message)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class NewsletterSubscribeView(APIView):
    """POST /api/newsletter/ — subscribe an email, idempotent. Open to everyone."""
    permission_classes = [AllowAny]

    def post(self, request):
        email = (request.data.get('email') or '').strip().lower()
        if not email:
            return Response({'email': ['This field is required.']}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_email(email)
        except DjangoValidationError:
            return Response({'email': ['Enter a valid email address.']}, status=status.HTTP_400_BAD_REQUEST)

        obj, created = NewsletterSubscriber.objects.get_or_create(email=email)
        serializer = NewsletterSubscriberSerializer(obj)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class SiteMetaView(APIView):
    """GET /api/meta/ — single call the frontend can use to hydrate the whole
    static part of the page (languages + services) in one round trip."""
    permission_classes = [AllowAny]

    def get(self, request):
        languages = LanguageSerializer(Language.objects.all(), many=True).data
        services = ServiceSerializer(Service.objects.filter(is_published=True), many=True).data
        testimonials = TestimonialSerializer(Testimonial.objects.filter(is_published=True), many=True).data
        return Response({
            'languages': languages,
            'services': services,
            'testimonials': testimonials,
        })