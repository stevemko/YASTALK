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
]
