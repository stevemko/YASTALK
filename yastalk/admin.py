import csv
from django.contrib import admin
from django.http import HttpResponse
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
    search_fields = ['name', 'email', 'subject', 'message']
    readonly_fields = ['name', 'email', 'subject', 'message', 'created_at']
    ordering = ['-created_at']


def export_subscribers_as_csv(modeladmin, request, queryset):
    """Admin action: select rows (or select-all) → download as CSV."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="yastalk_waitlist.csv"'
    writer = csv.writer(response)
    writer.writerow(['Email', 'Joined At'])
    for sub in queryset.order_by('-created_at'):
        writer.writerow([sub.email, sub.created_at.strftime('%Y-%m-%d %H:%M')])
    return response


export_subscribers_as_csv.short_description = "Export selected as CSV"


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ['email', 'created_at']
    search_fields = ['email']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    actions = [export_subscribers_as_csv]

   