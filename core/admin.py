from django.contrib import admin
from .models import Language, Service, TeamMember, Testimonial, ContactMessage, NewsletterSubscriber


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ['name_en', 'code', 'native_name', 'is_rtl', 'order']
    ordering = ['order']


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['title', 'icon', 'is_published', 'order']
    list_editable = ['is_published', 'order']


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ['name', 'role', 'order']


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ['author_name', 'language', 'is_published', 'order']
    list_editable = ['is_published', 'order']


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'subject', 'created_at', 'is_read']
    list_filter = ['is_read', 'created_at']
    readonly_fields = ['name', 'email', 'subject', 'message', 'created_at']


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ['email', 'created_at']
