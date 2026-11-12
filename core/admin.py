from django.contrib import admin
from .models import (
    Language, Service, TeamMember, Testimonial, ContactMessage, NewsletterSubscriber,
    Profile, LoginActivity, Payment, Event, Donation, Subscription,
)


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


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone', 'email_verified', 'created_at']
    list_filter = ['email_verified']
    list_editable = ['email_verified']      # tick this to confirm someone by hand
    search_fields = ['user__email', 'user__username', 'phone']
    readonly_fields = ['user', 'created_at']


@admin.register(LoginActivity)
class LoginActivityAdmin(admin.ModelAdmin):
    list_display = ['email_attempted', 'success', 'ip_address', 'created_at']
    list_filter = ['success', 'created_at']
    search_fields = ['email_attempted', 'ip_address']
    readonly_fields = ['user', 'email_attempted', 'success', 'ip_address', 'user_agent', 'created_at']

    def has_add_permission(self, request):
        return False


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'kind', 'starts_at', 'location', 'is_published']
    list_filter = ['kind', 'is_published', 'starts_at']
    list_editable = ['is_published']
    search_fields = ['title', 'summary', 'location']
    prepopulated_fields = {'slug': ('title',)}


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['plan', 'email', 'amount', 'status', 'mpesa_receipt', 'created_at']
    list_filter = ['status', 'plan', 'created_at']
    search_fields = ['email', 'phone', 'mpesa_receipt']
    readonly_fields = ['id', 'created_at', 'paid_at']


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ['method', 'display_amount', 'donor_name', 'status', 'created_at', 'paid_at']
    list_filter = ['method', 'status', 'created_at']
    search_fields = ['donor_name', 'donor_email', 'phone', 'mpesa_receipt', 'tx_hash']
    readonly_fields = ['id', 'created_at', 'paid_at']

    @admin.display(description='Amount (KSh)')
    def display_amount(self, obj):
        return obj.amount if obj.amount is not None else '—'


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'plan', 'active_until', 'updated_at']
    list_filter = ['plan', 'active_until']
    search_fields = ['user__email', 'user__username']
