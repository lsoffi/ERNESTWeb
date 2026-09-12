"""Private, operator-assisted privacy tools. No automatic identity attestation."""
import calendar
import json
import re
from datetime import date
from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.core import signing
from django.contrib.sessions.models import Session
from django.db import IntegrityError, transaction
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac
from .accounts import email_address
from .models import AccountEmail, Attempt, PrivacyOperation, RateBucket


def permitted(request):
    return (request.user.is_authenticated and request.user.is_active and request.user.is_staff
            and request.user.is_verified()
            and bool(settings.PRIVACY_OPERATOR_USERNAME)
            and request.user.username == settings.PRIVACY_OPERATOR_USERNAME)


def next_month(value):
    year = value.year + (value.month == 12)
    month = value.month % 12 + 1
    return value.replace(year=year, month=month, day=min(value.day, calendar.monthrange(year, month)[1]))


def account_context(user):
    return {'id': user.pk, 'nickname': user.username, 'email': user.email, 'joined': user.date_joined.isoformat()}


class PrivacyForm(forms.Form):
    account_token = forms.CharField(widget=forms.HiddenInput)
    reference = forms.RegexField(r'^[A-Za-z0-9_-]{3,64}$', label='Riferimento univoco della richiesta', max_length=64)
    received_on = forms.DateField(label='Ricevuta il', widget=forms.DateInput(attrs={'type': 'date'}))
    verification_method = forms.ChoiceField(label='Verifica effettuata', choices=[
        ('email', 'Conferma ricevuta dalla casella verificata dell’account'),
        ('authenticated', 'Richiesta già autenticata in modo adeguato'),
        ('alternative', 'Metodo alternativo concordato con il riferimento privacy'),
    ])
    verified_on = forms.DateField(label='Verificata il', widget=forms.DateInput(attrs={'type': 'date'}))
    evidence_checked = forms.BooleanField(label='Ho conservato il riscontro della verifica nella corrispondenza riservata')
    action = forms.ChoiceField(label='Operazione richiesta', choices=[('export', 'Scaricare copia dei dati'), ('correct', 'Rettificare nickname/email'), ('delete', 'Cancellare account e risultati')])
    confirm_username = forms.CharField(label='Riscrivi il nickname dell’account interessato')
    new_username = forms.CharField(label='Nuovo nickname (solo se richiesto)', required=False, max_length=24)
    new_email = forms.EmailField(label='Nuova email (solo se richiesta)', required=False, max_length=254)
    new_email_verified = forms.BooleanField(label='Ho verificato separatamente il controllo della nuova casella email', required=False)
    scope_checked = forms.BooleanField(label='Ho verificato l’ambito della richiesta e autorizzo questa specifica operazione')

    def __init__(self, *args, subject, **kwargs):
        self.subject = subject
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        try:
            expected = signing.loads(data.get('account_token', ''), salt='privacy-account', max_age=1800)
        except signing.BadSignature:
            raise forms.ValidationError('Pagina scaduta: ricarica e verifica nuovamente l’account.')
        if expected != account_context(self.subject):
            raise forms.ValidationError('Account modificato: ricarica e verifica nuovamente i dati.')
        today = timezone.localdate()
        if data.get('confirm_username') != self.subject.username:
            self.add_error('confirm_username', 'Il nickname non corrisponde.')
        if data.get('received_on', today) > today or data.get('verified_on', today) > today:
            raise forms.ValidationError('Le date non possono essere future.')
        if data.get('verified_on', today) < data.get('received_on', today):
            raise forms.ValidationError('La verifica non può precedere la richiesta.')
        if data.get('verification_method') == 'email' and not AccountEmail.objects.filter(user=self.subject, verified=True).exists():
            raise forms.ValidationError('Questo account non ha una casella verificata. Valuta un metodo alternativo.')
        if data.get('action') == 'correct':
            name = data.get('new_username', '').strip().lower()
            address = data.get('new_email', '')
            if not name and not address:
                raise forms.ValidationError('Indica almeno un dato da correggere.')
            if name:
                if not re.fullmatch(r'[a-z0-9_]{3,24}', name):
                    self.add_error('new_username', 'Usa 3–24 lettere, numeri o underscore.')
                elif User.objects.exclude(pk=self.subject.pk).filter(username=name).exists():
                    self.add_error('new_username', 'Nickname non disponibile.')
                data['new_username'] = name
            if address:
                address = email_address(address)
                data['new_email'] = address
                if not data.get('new_email_verified'):
                    self.add_error('new_email_verified', 'Conferma prima il controllo della nuova casella.')
                if AccountEmail.objects.exclude(user=self.subject).filter(address=address).exists():
                    self.add_error('new_email', 'Email non disponibile.')
        if PrivacyOperation.objects.filter(reference=data.get('reference')).exists():
            self.add_error('reference', 'Riferimento già utilizzato: consulta la ricevuta esistente.')
        return data


def sessions_for(user):
    # The signed session payload is never exported or logged.
    return [session for session in Session.objects.all().iterator()
            if str(session.get_decoded().get('_auth_user_id', '')) == str(user.pk)]


def download(payload, filename):
    response = HttpResponse(json.dumps(payload, ensure_ascii=False, indent=2, default=str), content_type='application/json; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def export_data(user):
    from .views import QUIZ_MAP, passport_for
    attempts = []
    best = {}
    for attempt in Attempt.objects.filter(user=user).order_by('created'):
        quiz = QUIZ_MAP.get(attempt.quiz, {})
        answers = []
        for number, choice in enumerate(attempt.answers):
            questions = quiz.get('questions', [])
            if number < len(questions) and isinstance(choice, int) and 0 <= choice < len(questions[number][1]):
                answers.append({'domanda': questions[number][0], 'risposta': questions[number][1][choice]})
        attempts.append({'quiz': attempt.quiz, 'creato_il': attempt.created, 'completato': attempt.finished,
                         'punteggio': attempt.score, 'risposte_temporanee': answers})
        if attempt.finished:
            best[attempt.quiz] = max(best.get(attempt.quiz, 0), attempt.score)
    return {'generato_il': timezone.now(), 'profilo': {'nickname': user.username, 'email': user.email,
            'email_confermata': AccountEmail.objects.filter(user=user, verified=True).exists(),
            'registrato_il': user.date_joined, 'ultimo_accesso': user.last_login, 'attivo': user.is_active},
            'tentativi': attempts, 'punteggio_totale': sum(best.values()),
            'timbri': [x['id'] for x in passport_for(best) if x['earned']],
            'sessioni': [{'scadenza': s.expire_date} for s in sessions_for(user)],
            'nota': 'Copia dei dati applicativi. Password, hash, token, chiavi di sessione e segreti MFA sono esclusi. Log e backup dei fornitori richiedono valutazione separata; accompagnare la copia con il riscontro privacy.'}


def privacy_member(site, request, user_id):
    if not permitted(request):
        return HttpResponseForbidden('Accesso riservato alla referente privacy con secondo fattore.')
    user = get_object_or_404(User, pk=user_id)
    if user.is_staff or user.is_superuser:
        return HttpResponseForbidden('Gli account amministrativi richiedono una gestione separata per preservare l’accesso di amministrazione.')
    form = PrivacyForm(request.POST or None, subject=user, initial={'received_on': timezone.localdate(), 'verified_on': timezone.localdate(), 'account_token': signing.dumps(account_context(user), salt='privacy-account')})
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        try:
            with transaction.atomic():
                # Same lock order as account verification and retention cleanup.
                entry = AccountEmail.objects.select_for_update().filter(user=user).first()
                user = User.objects.select_for_update().get(pk=user_id)
                if user.is_staff or user.is_superuser or account_context(user) != account_context(form.subject):
                    raise ValueError('Account modificato nel frattempo: ricarica la pagina.')
                if data['verification_method'] == 'email' and (not entry or not entry.verified):
                    raise ValueError('La verifica dell’email non è più valida.')
                operation = PrivacyOperation.objects.create(reference=data['reference'], actor=request.user, subject=user,
                    subject_id_at_request=user.pk, subject_joined_at=user.date_joined,
                    received_on=data['received_on'], verification_method=data['verification_method'], verified_on=data['verified_on'], action=data['action'])
                if data['action'] == 'export':
                    payload = export_data(user)
                    operation.result = {'verificato': True, 'tentativi_esportati': len(payload['tentativi']), 'consegna_da_confermare': True}
                elif data['action'] == 'correct':
                    if data.get('new_username'): user.username = data['new_username']
                    if data.get('new_email'):
                        user.email = data['new_email']
                        if entry is None: entry = AccountEmail(user=user)
                        entry.address = user.email
                        entry.verified = True
                        entry.save()
                    user.save(update_fields=['username', 'email'])
                    # Remove stored sessions after changing account identifiers.
                    Session.objects.filter(pk__in=[s.pk for s in sessions_for(user)]).delete()
                    saved = User.objects.get(pk=user.pk)
                    if saved.email != user.email or saved.username != user.username:
                        raise ValueError('Rettifica non verificata: operazione annullata.')
                    operation.result = {'verificato': True, 'nickname_rettificato': bool(data.get('new_username')), 'email_rettificata': bool(data.get('new_email'))}
                else:
                    target_id = user.pk
                    attempts_count = Attempt.objects.filter(user=user).count()
                    Session.objects.filter(pk__in=[s.pk for s in sessions_for(user)]).delete()
                    keys = ['auth-email:'+user.email, 'mail:'+user.email, 'leaderboard:'+str(user.pk)]
                    RateBucket.objects.filter(pk__in=[salted_hmac('ernest-rate-v2', '600:'+k, algorithm='sha256').hexdigest() for k in keys]).delete()
                    user.delete()
                    if User.objects.filter(pk=target_id).exists() or Attempt.objects.filter(user_id=target_id).exists() or AccountEmail.objects.filter(user_id=target_id).exists():
                        raise ValueError('Cancellazione non verificata: operazione annullata.')
                    operation.subject = None
                    operation.result = {'verificato': True, 'account_eliminati': 1, 'tentativi_eliminati': attempts_count, 'backup_e_log': 'Separati: non cancellati da questa operazione.'}
                operation.save(update_fields=['result', 'subject'])
            if data['action'] == 'export':
                return download(payload, f'ernest-dati-{operation.id}.json')
            return redirect(reverse('otpadmin:community_privacyoperation_change', args=[operation.pk]))
        except (IntegrityError, ValueError) as exc:
            form.add_error(None, str(exc) if isinstance(exc, ValueError) else 'Dati modificati o riferimento già usato. Ricarica e verifica prima di riprovare.')
    context = {**site.each_context(request), 'title': 'Gestisci richiesta privacy', 'subject': user, 'form': form,
               'operations': PrivacyOperation.objects.filter(subject=user).order_by('-performed_at'), 'opts': User._meta}
    return TemplateResponse(request, 'admin/privacy_member.html', context)


def receipt_payload(operation):
    payload = json.loads(json.dumps({
        'riferimento': operation.reference, 'ricevuta_il': operation.received_on,
        'scadenza_riscontro': next_month(operation.received_on),
        'metodo_verifica': operation.verification_method, 'verificata_il': operation.verified_on,
        'azione': operation.action, 'eseguita_il': operation.performed_at,
        'esito': operation.result, 'risposta_inviata_il': operation.replied_on,
        'account_id': operation.subject_id_at_request, 'account_creato_il': operation.subject_joined_at,
    }, default=str))
    payload['proof'] = signing.dumps(payload, salt='ernest-privacy-receipt')
    return payload
