from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from rest_framework import viewsets, mixins, generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Language, Service, TeamMember, Testimonial, ContactMessage, NewsletterSubscriber
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
    """POST /api/contact/ — enquiries need a logged-in account.

    The sender's name and email always come from the account, never from the
    request body, so nobody can send an enquiry pretending to be someone else.
    """
    queryset = ContactMessage.objects.all()
    serializer_class = ContactMessageSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        user = request.user
        data = request.data.copy()
        data['name'] = user.get_full_name() or user.email
        data['email'] = user.email
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=user)
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