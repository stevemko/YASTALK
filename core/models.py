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
