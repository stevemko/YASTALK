from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    LanguageViewSet,
    ServiceViewSet,
    TeamMemberViewSet,
    TestimonialViewSet,
    ContactMessageCreateView,
    NewsletterSubscribeView,
    SiteMetaView,
)
from .payment_views import InitiatePayment, MpesaCallback, PaymentStatus
from .extra_views import health, app_links

router = DefaultRouter()
router.register('languages', LanguageViewSet, basename='language')
router.register('services', ServiceViewSet, basename='service')
router.register('team', TeamMemberViewSet, basename='teammember')
router.register('testimonials', TestimonialViewSet, basename='testimonial')

urlpatterns = [
    path('', include(router.urls)),
    path('contact/', ContactMessageCreateView.as_view(), name='contact-create'),
    path('newsletter/', NewsletterSubscribeView.as_view(), name='newsletter-subscribe'),
    path('meta/', SiteMetaView.as_view(), name='site-meta'),

    path('health/', health, name='health'),
    path('app-links/', app_links, name='app-links'),

    path('payments/initiate/', InitiatePayment.as_view(), name='payment-initiate'),
    path('payments/mpesa/callback/<str:secret>/', MpesaCallback.as_view(), name='mpesa-callback'),
    path('payments/<uuid:pk>/status/', PaymentStatus.as_view(), name='payment-status'),
]