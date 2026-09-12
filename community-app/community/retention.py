"""Agreed retention policy; deadlines use Europe/Rome calendar time."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from django.http import JsonResponse
from django.utils import timezone

PROJECT_END = datetime(2028, 5, 1, tzinfo=ZoneInfo('Europe/Rome'))
UNVERIFIED_TTL = timedelta(days=7)
GUEST_TTL = timedelta(hours=24)
ANSWER_TTL = timedelta(hours=2)


def project_ended():
    return timezone.now() >= PROJECT_END


class RetentionDeadlineMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if project_ended() and request.path.startswith(('/api/', '/account/', '/admin/')):
            language = getattr(request, 'LANGUAGE_CODE', 'it').split('-')[0]
            message = {
                'it': 'La community ha concluso il periodo di attività.',
                'en': 'The community activity period has ended.',
                'fr': 'La période d’activité de la communauté est terminée.',
            }.get(language, 'La community ha concluso il periodo di attività.')
            return JsonResponse({'error': message}, status=410)
        return self.get_response(request)
