import hashlib
import json
import re
import time
from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from .i18n import tr
from .models import Attempt, RateBucket, AccountEmail
from .accounts import email_address, deliver, response as mail_response

QUIZZES = json.loads(Path(__file__).with_name('quizzes.json').read_text())
QUIZ_MAP = {q['id']: q for q in QUIZZES}

def error(message, status=400): return JsonResponse({'error': tr(message)}, status=status)

def body(request):
    try:
        value = json.loads(request.body)
        return value if isinstance(value, dict) else {}
    except (ValueError, UnicodeDecodeError): return {}

def limited(key, limit, period=600):
    key = hashlib.sha256(key.encode()).hexdigest()
    window = int(time.time()) // period
    with transaction.atomic():
        bucket, _ = RateBucket.objects.get_or_create(key=key)
        bucket = RateBucket.objects.select_for_update().get(pk=key)
        bucket.count = bucket.count + 1 if bucket.window == window else 1
        bucket.window = window
        bucket.save()
        return bucket.count > limit

def owned(request):
    if request.user.is_authenticated:
        return Attempt.objects.filter(user=request.user)
    if not request.session.session_key: return Attempt.objects.none()
    return Attempt.objects.filter(user=None, session_key=request.session.session_key)

def profile(request):
    results = owned(request).filter(finished=True).values('quiz').annotate(best=Max('score'))
    return {'name': request.user.username if request.user.is_authenticated else '', 'completed': {r['quiz']: r['best'] for r in results}}

@ensure_csrf_cookie
@require_GET
def index(request): return render(request, 'index.html', {'local_preview':settings.DEBUG, 'accounts_enabled':settings.ACCOUNTS_ENABLED})

@ensure_csrf_cookie
@require_GET
def state(request):
    public = [{**q, 'questions': [[v[0], v[1]] for v in q['questions']]} for q in QUIZZES]
    return JsonResponse({**profile(request), 'quizzes': public, 'accounts_enabled':settings.ACCOUNTS_ENABLED})

@require_POST
def auth(request, mode):
    if not settings.ACCOUNTS_ENABLED: return error('Registrazione e accesso saranno disponibili prossimamente.',503)
    if mode not in {'login', 'register'}: return error('Operazione non valida.', 404)
    data = body(request)
    try: email = email_address(data.get('email'))
    except ValidationError: return error('Inserisci un indirizzo email valido.')
    if limited('auth-ip:' + request.META.get('REMOTE_ADDR', ''), 40) or limited('auth-email:' + email, 10):
        return error('Troppi tentativi. Riprova tra dieci minuti.', 429)
    password = data.get('password', '')
    if not isinstance(password, str) or len(password) > 256: return error('Password non valida.')
    old_session = request.session.session_key
    if mode == 'register':
        name = data.get('username', '')
        if not isinstance(name,str) or not re.fullmatch(r'[a-z0-9_]{3,24}', name.strip().lower()):
            return error('Scegli un nickname di 3–24 lettere, numeri o underscore.')
        name = name.strip().lower()
        if AccountEmail.objects.filter(address=email).exists():
            return mail_response('Se hai già un account, accedi o usa il recupero password. Puoi anche richiedere un nuovo link di conferma.')
        form = UserCreationForm({'username':name,'password1':password,'password2':data.get('password2','')})
        if not form.is_valid(): return error(' '.join(str(e) for es in form.errors.values() for e in es))
        try:
            with transaction.atomic():
                user = form.save(commit=False)
                user.email = email
                user.is_active = False
                user.save()
                AccountEmail.objects.create(user=user,address=email)
        except IntegrityError: return error('Impossibile creare il profilo con questi dati. Prova ad accedere o scegli un altro nickname.')
        try: url = deliver(user,'verify')
        except Exception:
            return error('Profilo creato, ma invio non riuscito. Usa “Reinvia conferma” per riprovare.',503)
        return mail_response('Controlla la posta e conferma il tuo indirizzo prima di accedere.',url)
    else:
        entry = AccountEmail.objects.select_related('user').filter(address=email,verified=True).first()
        # Run the password hasher even for an unknown email.
        user = authenticate(request,username=entry.user.username if entry else '__unknown_email__',password=password)
        if entry is None or user is None: return error('Email o password non corrette, oppure email non ancora confermata.',401)
    login(request, user)
    if old_session:
        Attempt.objects.filter(user=None, session_key=old_session).update(user=user)
    return JsonResponse(profile(request))

@require_POST
def signout(request):
    logout(request)
    return JsonResponse(profile(request))

@require_POST
def start(request):
    quiz = body(request).get('quiz')
    if not isinstance(quiz, str) or quiz not in QUIZ_MAP: return error('Quiz non trovato.', 404)
    if not request.session.session_key: request.session.create()
    if limited('quiz:' + request.session.session_key, 60): return error('Troppe nuove sfide. Riprova più tardi.', 429)
    attempt = Attempt.objects.create(quiz=quiz, session_key=request.session.session_key, user=request.user if request.user.is_authenticated else None)
    return JsonResponse({'attempt': str(attempt.id)})

@require_POST
def answer(request):
    data = body(request)
    with transaction.atomic():
        try: attempt = owned(request).select_for_update().get(pk=data.get('attempt'))
        except (Attempt.DoesNotExist, ValueError, TypeError, ValidationError): return error('Sfida non trovata.', 404)
        if attempt.finished or attempt.created < timezone.now() - timedelta(hours=2):
            return error('Sfida terminata o scaduta. Inizia un nuovo quiz.', 409)
        index = len(attempt.answers)
        if type(data.get('index')) is not int or data['index'] != index: return error('Risposta già registrata. Riparti dal quiz.', 409)
        q = QUIZ_MAP[attempt.quiz]['questions'][index]
        choice = data.get('answer')
        if type(choice) is not int or not 0 <= choice < len(q[1]): return error('Scegli una risposta valida.')
        attempt.answers.append(choice)
        attempt.score += 10 if choice == q[2] else 0
        attempt.finished = len(attempt.answers) == len(QUIZ_MAP[attempt.quiz]['questions'])
        attempt.save()
    return JsonResponse({'correct': q[2], 'explanation': q[3], 'score': attempt.score, 'finished': attempt.finished, **profile(request)})


@require_GET
def leaderboard(request):
    if not request.user.is_authenticated:
        result = error('Accedi per vedere la classifica.', 401)
        result['Cache-Control'] = 'private, no-store'
        return result
    best = Attempt.objects.filter(
        finished=True, user__is_active=True, user__accountemail__verified=True
    ).values('user_id', 'quiz').annotate(best=Max('score'))
    totals = {}
    for row in best:
        totals[row['user_id']] = totals.get(row['user_id'], 0) + row['best']
    # Fixed score bands publish aggregate counts only, never member identifiers.
    maximum = max(len(QUIZZES) * 30, max(totals.values(), default=0))
    bands = [{'minimum': n, 'maximum': n + 9, 'count': 0} for n in range(0, maximum + 1, 10)]
    for score in totals.values():
        bands[score // 10]['count'] += 1
    mine = None
    if request.user.is_authenticated and request.user.pk in totals:
        score = totals[request.user.pk]
        mine = {'score': score, 'rank': 1 + sum(total > score for total in totals.values())}
    result = JsonResponse({'bands': bands, 'participants': len(totals), 'mine': mine})
    result['Cache-Control'] = 'private, no-store'
    return result
