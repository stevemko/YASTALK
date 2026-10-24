from django.contrib import admin
from .models import (
    Language, Service, TeamMember, Testimonial, ContactMessage, NewsletterSubscriber,
    Profile, LoginActivity, Event, Payment, Donation, Subscription,
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
    """Post and edit the events shown on the website. Untick is_published to keep a draft."""
    list_display = ['title', 'kind', 'starts_at', 'location', 'is_published']
    list_filter = ['kind', 'is_published']
    list_editable = ['is_published']
    search_fields = ['title', 'summary', 'location']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'starts_at'


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'user', 'plan', 'amount', 'status', 'mpesa_receipt']
    list_filter = ['status', 'plan']
    search_fields = ['email', 'phone', 'mpesa_receipt']
    readonly_fields = [f.name for f in Payment._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    """Crypto gifts arrive as 'pending': check the hash on bscscan.com, then set the amount and status."""
    list_display = ['created_at', 'method', 'donor_name', 'amount', 'status', 'is_anonymous']
    list_filter = ['method', 'status', 'is_anonymous']
    search_fields = ['donor_name', 'donor_email', 'phone', 'mpesa_receipt', 'tx_hash', 'provider_ref']
    readonly_fields = ['id', 'method', 'phone', 'provider_ref', 'mpesa_receipt', 'tx_hash', 'created_at']


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """Give or extend access by hand (for example for a gift or a refund) by editing active_until."""
    list_display = ['user', 'plan', 'active_until']
    search_fields = ['user__email']
