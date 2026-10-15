import csv

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.http import HttpResponse

from .models import (
    ContactMessage,
    Event,
    Language,
    LoginActivity,
    NewsletterSubscriber,
    Payment,
    Profile,
    Service,
    TeamMember,
    Testimonial,
)

User = get_user_model()


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


@admin.action(description="Export selected as CSV")
def export_subscribers_as_csv(modeladmin, request, queryset):
    """Admin action: select rows (or select-all) -> download as CSV."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="yastalk_waitlist.csv"'
    writer = csv.writer(response)
    writer.writerow(['Email', 'Joined At'])
    for sub in queryset.order_by('-created_at'):
        writer.writerow([sub.email, sub.created_at.strftime('%Y-%m-%d %H:%M')])
    return response


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ['email', 'created_at']
    search_fields = ['email']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    actions = [export_subscribers_as_csv]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'created_at', 'plan', 'amount', 'phone', 'email',
        'status', 'mpesa_receipt', 'result_desc',
    ]
    list_filter = ['status', 'plan', 'created_at']
    search_fields = ['email', 'phone', 'mpesa_receipt', 'checkout_request_id']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    # Payments are created by the website and updated by Safaricom's callback,
    # so every field is read-only in the admin.
    readonly_fields = [
        'id', 'email', 'phone', 'plan', 'amount', 'status',
        'checkout_request_id', 'mpesa_receipt', 'result_desc',
        'created_at', 'paid_at',
    ]

    def has_add_permission(self, request):
        return False        # nobody should create a "paid" record by hand


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'kind', 'starts_at', 'location', 'is_published']
    list_filter = ['kind', 'is_published', 'starts_at']
    list_editable = ['is_published']
    search_fields = ['title', 'summary', 'location']
    prepopulated_fields = {'slug': ('title',)}      # slug fills in as you type the title
    date_hierarchy = 'starts_at'


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False


admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [ProfileInline]
    list_display = [
        'email', 'first_name', 'last_name',
        'is_active', 'is_staff', 'date_joined', 'last_login',
    ]
    list_filter = ['is_active', 'is_staff', 'date_joined']
    search_fields = ['email', 'first_name', 'last_name', 'profile__phone']
    ordering = ['-date_joined']
    actions = ['deactivate_users', 'activate_users']

    @admin.action(description='Deactivate selected users (they can no longer log in)')
    def deactivate_users(self, request, queryset):
        queryset.exclude(is_superuser=True).update(is_active=False)

    @admin.action(description='Re-activate selected users')
    def activate_users(self, request, queryset):
        queryset.update(is_active=True)


@admin.register(LoginActivity)
class LoginActivityAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'email_attempted', 'success', 'ip_address', 'user']
    list_filter = ['success', 'created_at']
    search_fields = ['email_attempted', 'ip_address']
    date_hierarchy = 'created_at'
    readonly_fields = [
        'user', 'email_attempted', 'success',
        'ip_address', 'user_agent', 'created_at',
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False        # an audit log should not be editable