from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET


@require_GET
def health(request):
    """Cheap endpoint for uptime pings (no database hit)."""
    return JsonResponse({'status': 'ok'})


@require_GET
@cache_page(60 * 10)
def app_links(request):
    """Direct URLs to the app being built. Only filled-in links are returned."""
    return JsonResponse({k: v for k, v in settings.APP_LINKS.items() if v})