from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    LanguageViewSet,
    ServiceViewSet,
    TeamMemberViewSet,
    TestimonialViewSet,
    ContactMessageCreateView,
    NewsletterSubscribeView,
    SiteMetaView,
)

from .auth_views import (
    RegisterView,
    LoginView,
    LogoutView,
    MeView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    VerifyEmailView,
    ResendVerificationView,
    ChangePasswordView,
)

from .extra_views import health, app_links
from .event_views import EventListView, EventDetailView
from .donation_views import (
    DonationConfig, DonateMpesa, DonationStatus, DonateCard, VerifyCard,
    PaystackWebhook, DonateCrypto,
)
from .payment_views import (
    InitiatePayment,
    PlanList,
    MpesaCallback,
    PaymentStatus,
    PaymentHistory,
)

router = DefaultRouter()
router.register(r'languages', LanguageViewSet, basename='language')
router.register(r'services', ServiceViewSet, basename='service')
router.register(r'team', TeamMemberViewSet, basename='teammember')
router.register(r'testimonials', TestimonialViewSet, basename='testimonial')

urlpatterns = [
    path('', include(router.urls)),

    # Website content
    path('contact/', ContactMessageCreateView.as_view(), name='contact-create'),
    path('newsletter/', NewsletterSubscribeView.as_view(), name='newsletter-subscribe'),
    path('meta/', SiteMetaView.as_view(), name='site-meta'),

    # Site utilities
    path('health/', health, name='health'),
    path('app-links/', app_links, name='app-links'),

    # Authentication
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/logout/', LogoutView.as_view(), name='auth-logout'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='auth-refresh'),
    path('auth/me/', MeView.as_view(), name='auth-me'),
    path('auth/verify-email/', VerifyEmailView.as_view(), name='auth-verify-email'),
    path('auth/resend-verification/', ResendVerificationView.as_view(), name='auth-resend-verification'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='auth-change-password'),
    path(
        'auth/password-reset/',
        PasswordResetRequestView.as_view(),
        name='auth-password-reset'
    ),
    path(
        'auth/password-reset/confirm/',
        PasswordResetConfirmView.as_view(),
        name='auth-password-reset-confirm'
    ),

    # Payments
    path('payments/', PaymentHistory.as_view(), name='payment-history'),
    path('events/', EventListView.as_view(), name='event-list'),
    path('events/<slug:slug>/', EventDetailView.as_view(), name='event-detail'),

    path('donations/config/', DonationConfig.as_view(), name='donation-config'),
    path('donations/mpesa/', DonateMpesa.as_view(), name='donation-mpesa'),
    path('donations/<uuid:pk>/status/', DonationStatus.as_view(), name='donation-status'),
    path('donations/card/', DonateCard.as_view(), name='donation-card'),
    path('donations/card/verify/', VerifyCard.as_view(), name='donation-card-verify'),
    path('donations/paystack/webhook/', PaystackWebhook.as_view(), name='donation-paystack-webhook'),
    path('donations/crypto/', DonateCrypto.as_view(), name='donation-crypto'),

    path('payments/plans/', PlanList.as_view(), name='payment-plans'),
    path('payments/initiate/', InitiatePayment.as_view(), name='payment-initiate'),
    path(
        'payments/mpesa/callback/<str:secret>/',
        MpesaCallback.as_view(),
        name='mpesa-callback'
    ),
    path(
        'payments/<uuid:pk>/status/',
        PaymentStatus.as_view(),
        name='payment-status'
    ),
]
