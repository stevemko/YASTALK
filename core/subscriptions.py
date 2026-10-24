from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import Subscription


def extend_subscription(user, plan):
    """Called when a plan payment succeeds. Each payment buys SUBSCRIPTION_DAYS more days.
    Paying while still active adds on top of the time left, so nobody loses days by renewing early.
    Call this inside the same transaction that marks the payment as paid."""
    now = timezone.now()
    sub, _ = Subscription.objects.select_for_update().get_or_create(
        user=user, defaults={'plan': plan, 'active_until': now},
    )
    start = sub.active_until if sub.active_until > now else now
    sub.plan = plan
    sub.active_until = start + timedelta(days=settings.SUBSCRIPTION_DAYS)
    sub.save()
    return sub


def subscription_payload(user):
    """What the website and the mobile app read to know if the account is a paying one."""
    sub = Subscription.objects.filter(user=user).first()
    if not sub:
        return None
    return {
        'plan': sub.plan,
        'active_until': sub.active_until,
        'active': sub.active_until > timezone.now(),
    }
