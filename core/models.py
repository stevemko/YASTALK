import uuid

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models


class Language(models.Model):
    """One of the languages YasTalk translates between."""
    code = models.CharField(max_length=5, unique=True, help_text="e.g. en, fr, ln, sw, ar")
    name_en = models.CharField(max_length=50, help_text="English name, e.g. 'Swahili'")
    native_name = models.CharField(max_length=50, help_text="Name in its own script, e.g. 'Kiswahili'")
    flag_emoji = models.CharField(max_length=10, blank=True)
    is_rtl = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name_en']

    def __str__(self):
        return f"{self.name_en} ({self.code})"


class Service(models.Model):
    """A feature/service card shown on the site, e.g. 'Voice Translation'."""
    ICON_CHOICES = [
        ('mic', 'Microphone'),
        ('text', 'Text'),
        ('camera', 'Camera'),
        ('offline', 'Offline'),
        ('chat', 'Conversation'),
        ('document', 'Document'),
    ]
    icon = models.CharField(max_length=20, choices=ICON_CHOICES, default='text')
    title = models.CharField(max_length=100)
    description = models.TextField()
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


class TeamMember(models.Model):
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=100)
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to='team/', blank=True, null=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name


class Testimonial(models.Model):
    author_name = models.CharField(max_length=100)
    author_role = models.CharField(max_length=100, blank=True)
    quote = models.TextField()
    language = models.ForeignKey(Language, on_delete=models.SET_NULL, null=True, blank=True)
    is_published = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.author_name} — {self.quote[:40]}"


class ContactMessage(models.Model):
    """An enquiry. Sent by a logged-in account; name and email come from the account."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='enquiries',
    )
    name = models.CharField(max_length=120)
    email = models.EmailField()
    subject = models.CharField(max_length=150, blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} <{self.email}> - {self.created_at:%Y-%m-%d}"


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


class Payment(models.Model):
    """A payment made through the website (M-Pesa STK Push via Daraja)."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'

    phone_validator = RegexValidator(
        regex=r'^254[17]\d{8}$',
        message="Phone must be in the format 2547XXXXXXXX or 2541XXXXXXXX",
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='payments',
    )
    email = models.EmailField()
    phone = models.CharField(max_length=12, validators=[phone_validator])
    plan = models.CharField(max_length=30)
    amount = models.PositiveIntegerField(help_text="Amount in KSh, always set by the server")
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    checkout_request_id = models.CharField(max_length=100, blank=True, db_index=True)
    mpesa_receipt = models.CharField(max_length=30, blank=True)
    result_desc = models.CharField(
        max_length=200, blank=True,
        help_text="Safaricom's message, e.g. why a payment failed or was cancelled",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone', 'plan', 'status']),   # duplicate-payment check
        ]

    def __str__(self):
        return f"{self.plan} - KSh {self.amount} - {self.phone} [{self.status}]"


class Event(models.Model):
    """An event shown on the website (webinar, meetup, launch...)."""

    class Kind(models.TextChoices):
        WEBINAR = 'webinar', 'Webinar'
        MEETUP = 'meetup', 'Meetup'
        LAUNCH = 'launch', 'Launch'
        WORKSHOP = 'workshop', 'Workshop'
        OTHER = 'other', 'Other'

    title = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.OTHER)
    summary = models.CharField(max_length=200, help_text="One-line teaser for cards")
    description = models.TextField(blank=True)
    location = models.CharField(max_length=150, blank=True, help_text="Venue, or 'Online'")
    online_url = models.URLField(blank=True, help_text="Meeting or livestream link")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    image = models.ImageField(upload_to='events/', blank=True, null=True)
    registration_url = models.URLField(blank=True)
    is_published = models.BooleanField(default=False, help_text="Untick to keep as a draft")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['starts_at']

    def __str__(self):
        return f"{self.title} ({self.starts_at:%Y-%m-%d})"


class Profile(models.Model):
    """Extra data for a website account. Only collect what you really need."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile'
    )
    phone = models.CharField(max_length=15, blank=True)
    email_verified = models.BooleanField(default=False)
    preferred_language = models.ForeignKey(
        Language, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Profile of {self.user.username}"


class LoginActivity(models.Model):
    """One row per login attempt: who, when, from where, and whether it worked."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    email_attempted = models.CharField(max_length=254, db_index=True)
    success = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'login activity'
        indexes = [models.Index(fields=['email_attempted', 'success', 'created_at'])]

    def __str__(self):
        status = 'ok' if self.success else 'failed'
        return f"{self.email_attempted} - {status} - {self.created_at:%Y-%m-%d %H:%M}"