from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, serializers
from rest_framework.permissions import AllowAny

from .models import Event


class EventSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source='get_kind_display', read_only=True)
    is_past = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            'id', 'title', 'slug', 'kind', 'kind_label', 'summary', 'description',
            'location', 'online_url', 'starts_at', 'ends_at', 'image',
            'registration_url', 'is_past',
        ]

    def get_is_past(self, obj):
        return (obj.ends_at or obj.starts_at) < timezone.now()


class EventListView(generics.ListAPIView):
    """GET /api/events/?when=upcoming (default) | past | all  -- published events only."""
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = EventSerializer

    def get_queryset(self):
        now = timezone.now()
        qs = Event.objects.filter(is_published=True)
        when = self.request.query_params.get('when', 'upcoming')
        ongoing_or_future = Q(ends_at__gte=now) | Q(ends_at__isnull=True, starts_at__gte=now)
        if when == 'past':
            return qs.exclude(ongoing_or_future).order_by('-starts_at')[:50]
        if when == 'all':
            return qs.order_by('-starts_at')[:100]
        return qs.filter(ongoing_or_future).order_by('starts_at')


class EventDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = EventSerializer
    queryset = Event.objects.filter(is_published=True)
    lookup_field = 'slug'
