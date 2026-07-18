from rest_framework import serializers
from .models import Language, Service, TeamMember, Testimonial, ContactMessage, NewsletterSubscriber


class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = ['id', 'code', 'name_en', 'native_name', 'flag_emoji', 'is_rtl', 'order']


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ['id', 'icon', 'title', 'description', 'order']


class TeamMemberSerializer(serializers.ModelSerializer):
    photo = serializers.SerializerMethodField()

    class Meta:
        model = TeamMember
        fields = ['id', 'name', 'role', 'bio', 'photo', 'order']

    def get_photo(self, obj):
        if obj.photo:
            request = self.context.get('request')
            url = obj.photo.url
            return request.build_absolute_uri(url) if request else url
        return None


class TestimonialSerializer(serializers.ModelSerializer):
    language_code = serializers.CharField(source='language.code', read_only=True, default=None)

    class Meta:
        model = Testimonial
        fields = ['id', 'author_name', 'author_role', 'quote', 'language_code', 'order']


class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ['id', 'name', 'email', 'subject', 'message', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_message(self, value):
        if len(value.strip()) < 10:
            raise serializers.ValidationError("Message must be at least 10 characters long.")
        return value


class NewsletterSubscriberSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterSubscriber
        fields = ['id', 'email', 'created_at']
        read_only_fields = ['id', 'created_at']
