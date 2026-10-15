from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.permissions import AllowAny

from .models import Event


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = [
            'id', 'title', 'slug', 'kind', 'summary', 'description', 'location',
            'online_url', 'starts_at', 'ends_at', 'image', 'registration_url',
        ]


class EventViewSet(viewsets.ReadOnlyModelViewSet):
    """Public list of published events. Use ?when=upcoming or ?when=past."""
    serializer_class = EventSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    lookup_field = 'slug'

    def get_queryset(self):
        qs = Event.objects.filter(is_published=True)
        when = self.request.query_params.get('when')
        now = timezone.now()
        if when == 'upcoming':
            return qs.filter(starts_at__gte=now).order_by('starts_at')
        if when == 'past':
            return qs.filter(starts_at__lt=now).order_by('-starts_at')
        return qs