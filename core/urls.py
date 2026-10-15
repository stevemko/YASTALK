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
from .auth_views import RegisterView, LoginView, LogoutView, MeView
from .event_views import EventViewSet
from .extra_views import health, app_links
from .payment_views import InitiatePayment, MpesaCallback, PaymentStatus

router = DefaultRouter()
router.register('languages', LanguageViewSet, basename='language')
router.register('services', ServiceViewSet, basename='service')
router.register('team', TeamMemberViewSet, basename='teammember')
router.register('testimonials', TestimonialViewSet, basename='testimonial')
router.register('events', EventViewSet, basename='event')

urlpatterns = [
    path('', include(router.urls)),
    path('contact/', ContactMessageCreateView.as_view(), name='contact-create'),
    path('newsletter/', NewsletterSubscribeView.as_view(), name='newsletter-subscribe'),
    path('meta/', SiteMetaView.as_view(), name='site-meta'),

    # site utilities
    path('health/', health, name='health'),
    path('app-links/', app_links, name='app-links'),

    # website accounts
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/logout/', LogoutView.as_view(), name='auth-logout'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='auth-refresh'),
    path('auth/me/', MeView.as_view(), name='auth-me'),

    # payments (M-Pesa / Daraja)
    path('payments/initiate/', InitiatePayment.as_view(), name='payment-initiate'),
    path('payments/mpesa/callback/<str:secret>/', MpesaCallback.as_view(), name='mpesa-callback'),
    path('payments/<uuid:pk>/status/', PaymentStatus.as_view(), name='payment-status'),
]