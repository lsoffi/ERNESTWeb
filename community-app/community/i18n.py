import json
from pathlib import Path
from django.utils import translation

LANGUAGES = ('it', 'fr', 'en')
CATALOGS = json.loads(Path(__file__).with_name('translations.json').read_text())


def tr(text):
    language = translation.get_language().split('-')[0]
    return CATALOGS.get(language, {}).get(text, text)


def context(request):
    return {'language': translation.get_language().split('-')[0], 'catalogs': CATALOGS}


class EmailLanguageMiddleware:
    """Email links preserve their language even when opened in another browser."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        language = request.GET.get('lang')
        if language in LANGUAGES:
            translation.activate(language)
            request.LANGUAGE_CODE = language
        response = self.get_response(request)
        if language in LANGUAGES:
            response.set_cookie("django_language", language, max_age=31536000, samesite="Lax", secure=request.is_secure())
        return response
