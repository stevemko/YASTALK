from rest_framework import viewsets, mixins, generics, status
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


class ServiceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Service.objects.filter(is_published=True)
    serializer_class = ServiceSerializer


class TeamMemberViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = TeamMember.objects.all()
    serializer_class = TeamMemberSerializer


class TestimonialViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Testimonial.objects.filter(is_published=True)
    serializer_class = TestimonialSerializer


class ContactMessageCreateView(generics.CreateAPIView):
    """POST /api/contact/ — public contact form submission."""
    queryset = ContactMessage.objects.all()
    serializer_class = ContactMessageSerializer


class NewsletterSubscribeView(APIView):
    """POST /api/newsletter/ — subscribe an email, idempotent."""

    def post(self, request):
        email = (request.data.get('email') or '').strip().lower()
        if not email:
            return Response({'email': ['This field is required.']}, status=status.HTTP_400_BAD_REQUEST)

        obj, created = NewsletterSubscriber.objects.get_or_create(email=email)
        serializer = NewsletterSubscriberSerializer(obj)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class SiteMetaView(APIView):
    """GET /api/meta/ — single call the frontend can use to hydrate the whole
    static part of the page (languages + services) in one round trip."""

    def get(self, request):
        languages = LanguageSerializer(Language.objects.all(), many=True).data
        services = ServiceSerializer(Service.objects.filter(is_published=True), many=True).data
        testimonials = TestimonialSerializer(Testimonial.objects.filter(is_published=True), many=True).data
        return Response({
            'languages': languages,
            'services': services,
            'testimonials': testimonials,
        })
