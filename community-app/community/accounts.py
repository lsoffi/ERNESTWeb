from urllib.parse import urlencode
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.cache import never_cache
from .i18n import tr
from django.utils.translation import get_language
from .models import AccountEmail


def email_address(value):
    if not isinstance(value, str): raise ValidationError('Email non valida.')
    value = value.strip().lower()
    validate_email(value)
    if len(value) > 254: raise ValidationError('Email troppo lunga.')
    return value


def deliver(user, purpose):
    if purpose == 'verify':
        token = signing.dumps({'user':user.pk, 'email':user.email}, salt='ernest-verify')
        path = '/account/verify/?' + urlencode({'token':token, 'lang':get_language().split('-')[0]})
        subject = 'Conferma la tua email — ERNEST'
        text = 'Conferma il tuo indirizzo email entro 24 ore per attivare il profilo ERNEST.'
    else:
        path = '/account/reset/?' + urlencode({'uid':user.pk, 'token':default_token_generator.make_token(user), 'lang':get_language().split('-')[0]})
        subject = 'Reimposta la password — ERNEST'
        text = 'Puoi scegliere una nuova password entro un’ora. Se non hai richiesto il cambio, ignora questa email.'
    url = settings.PUBLIC_BASE_URL.rstrip('/') + path
    send_mail(tr(subject), tr(text)+'\n\n'+url, settings.DEFAULT_FROM_EMAIL, [user.email])
    return url


def response(message, url=None):
    data = {'message':tr(message)}
    if settings.DEBUG and url: data['preview_url'] = url
    return JsonResponse(data)

@require_POST
def request_mail(request, purpose):
    from .views import body, error, limited
    if not settings.ACCOUNTS_ENABLED: return error('Invio email non ancora attivo.',503)
    if purpose not in {'verify', 'reset'}: return error('Operazione non valida.',404)
    try: email = email_address(body(request).get('email'))
    except ValidationError: return error('Inserisci un indirizzo email valido.')
    if limited('mail-ip:'+request.META.get('REMOTE_ADDR',''),20) or limited('mail:'+email,3):
        return error('Troppi invii richiesti. Riprova tra dieci minuti.',429)
    entry = AccountEmail.objects.select_related('user').filter(address=email).first()
    url = None
    if entry and ((purpose == 'verify' and not entry.verified) or (purpose == 'reset' and entry.verified and entry.user.is_active)):
        try: url = deliver(entry.user,purpose)
        except Exception:
            # Do not disclose account existence or mail-provider details.
            import logging
            logging.getLogger(__name__).error('Account email delivery failed')
    return response('Se l’indirizzo corrisponde a un account idoneo, riceverai un link. Controlla anche la posta indesiderata.',url)

@never_cache
@require_http_methods(['GET','POST'])
def verify(request):
    token = request.POST.get('token') if request.method == 'POST' else request.GET.get('token')
    valid = False
    try:
        data = signing.loads(token or '',salt='ernest-verify',max_age=86400)
        with transaction.atomic():
            entry = AccountEmail.objects.select_for_update().get(user_id=data['user'],address=data['email'],verified=False)
            valid = True
            if request.method == 'POST':
                entry.verified = True
                entry.save()
                entry.user.is_active = True
                entry.user.save(update_fields=['is_active'])
    except (signing.BadSignature, AccountEmail.DoesNotExist, KeyError, TypeError): pass
    return render(request,'account.html',{'kind':'verify','valid':valid,'done':valid and request.method=='POST','token':token})

@never_cache
@require_http_methods(['GET','POST'])
def reset(request):
    uid = request.POST.get('uid') if request.method == 'POST' else request.GET.get('uid')
    token = request.POST.get('token') if request.method == 'POST' else request.GET.get('token')
    done = False
    form = None
    with transaction.atomic():
        try: user = User.objects.select_for_update().get(pk=uid,is_active=True,accountemail__verified=True)
        except (User.DoesNotExist, ValueError, TypeError): user = None
        valid = user is not None and default_token_generator.check_token(user,token)
        if valid:
            form = SetPasswordForm(user,request.POST if request.method=='POST' else None)
            if request.method=='POST' and form.is_valid():
                form.save()
                done = True
    return render(request,'account.html',{'kind':'reset','valid':valid,'done':done,'token':token,'uid':uid,'form':form})
