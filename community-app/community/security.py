"""Application-side abuse controls. Forwarded addresses are untrusted by default."""
import ipaddress
import time
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.utils.crypto import salted_hmac
from .models import RateBucket
from .i18n import tr


def client_address(request):
    try:
        peer = ipaddress.ip_address(request.META.get('REMOTE_ADDR', ''))
    except ValueError:
        return 'unknown'
    networks = [ipaddress.ip_network(value) for value in settings.TRUSTED_PROXY_CIDRS]
    def trusted(address):
        return any(address in network for network in networks)
    if not trusted(peer):
        return str(peer)
    # Walk from the actual peer towards the client, discarding only known proxies.
    # Never trust an arbitrary X-Forwarded-For value supplied by the browser.
    parts = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')
    if len(parts) > 16:
        return str(peer)
    try:
        chain = [ipaddress.ip_address(part.strip()) for part in parts if part.strip()] + [peer]
    except ValueError:
        return str(peer)
    while len(chain) > 1 and trusted(chain[-1]):
        chain.pop()
    return str(chain[-1])


def limited(key, limit, period=600):
    digest = salted_hmac('ernest-rate-v2', str(period) + ':' + key, algorithm='sha256').hexdigest()
    window = int(time.time()) // period
    with transaction.atomic():
        RateBucket.objects.get_or_create(key=digest)
        bucket = RateBucket.objects.select_for_update().get(pk=digest)
        bucket.count = min(bucket.count + 1, limit + 1) if bucket.window == window else 1
        bucket.window = window
        bucket.save(update_fields=['count', 'window'])
        return bucket.count > limit


def rate_error():
    result = JsonResponse({'error': tr('Troppi tentativi. Riprova tra dieci minuti.')}, status=429)
    result['Retry-After'] = '600'
    result['Cache-Control'] = 'private, no-store'
    return result


class AbuseProtectionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        category = None
        if request.method == 'POST':
            if path.startswith('/api/auth/') or path == '/admin/login/':
                category, limit = 'auth', (10 if path == '/admin/login/' else 40)
            elif path.startswith('/api/mail/'):
                category, limit = 'mail', 20
            elif path.startswith('/account/'):
                category, limit = 'account', 60
            elif path in ('/api/start/', '/api/answer/'):
                category, limit = 'quiz', 600
        if category:
            # Read with a small cap even if Content-Length is absent or inaccurate.
            payload = request.read(settings.COMMUNITY_MAX_BODY_BYTES + 1)
            if len(payload) > settings.COMMUNITY_MAX_BODY_BYTES:
                return JsonResponse({'error': tr('Richiesta troppo grande.')}, status=413)
            from io import BytesIO
            request._body = payload
            request._stream = BytesIO(payload)
            address = client_address(request)
            if limited('request:' + category + ':' + address, limit):
                return rate_error()
            if path == '/api/start/' and limited('quiz-start-ip:' + address, 120):
                return rate_error()
        elif path == '/api/leaderboard/' and request.user.is_authenticated:
            if limited('leaderboard:' + str(request.user.pk), 120):
                return rate_error()
        response = self.get_response(request)
        if path.startswith(('/api/', '/account/', '/admin/')):
            response['Cache-Control'] = 'private, no-store'
        return response
