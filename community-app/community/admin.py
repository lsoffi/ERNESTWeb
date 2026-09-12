from django.contrib import admin
from django_otp.admin import OTPAdminSite
from django.contrib.auth.models import User
from django.db.models import Prefetch
from django.http import HttpResponse
from .models import Attempt, PrivacyOperation
from django.urls import path, reverse
from django.utils.html import format_html
from .privacy import permitted, privacy_member, download, next_month, receipt_payload
from django.shortcuts import get_object_or_404
from django.http import HttpResponseForbidden
from django import forms
from django.utils import timezone


class CommunityAdminSite(OTPAdminSite):
    site_header = 'ERNEST — Gestione community'
    site_title = 'ERNEST amministrazione'
    index_title = 'Account e risultati'
    site_url = '/'

    def get_urls(self):
        return [
            path('privacy/member/<int:user_id>/', self.admin_view(lambda request, user_id: privacy_member(self, request, user_id)), name='privacy_member'),
            path('privacy/receipt/<uuid:operation_id>/', self.admin_view(self.privacy_receipt), name='privacy_receipt'),
        ] + super().get_urls()

    def privacy_receipt(self, request, operation_id):
        if not permitted(request):
            return HttpResponseForbidden('Accesso riservato.')
        operation = get_object_or_404(PrivacyOperation, pk=operation_id)
        return download(receipt_payload(operation), f'ernest-ricevuta-{operation.id}.json')

    def login(self, request, extra_context=None):
        response = super().login(request, extra_context)
        if request.user.is_authenticated and request.session.get('otp_device_id'):
            request.session.set_expiry(30 * 60)
        return response



community_admin = CommunityAdminSite(name='otpadmin')


@admin.register(User, site=community_admin)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'email_verified', 'date_joined', 'last_login', 'completed_quizzes', 'total_score', 'is_active')
    search_fields = ('username', 'email')
    list_filter = ('accountemail__verified', 'is_active', 'date_joined')
    ordering = ('-date_joined',)
    list_per_page = 50
    fields = ('username', 'email', 'email_verified', 'date_joined', 'last_login', 'completed_quizzes', 'total_score', 'is_active')
    readonly_fields = fields[:-1] + ('privacy_tools',)
    fields = fields + ('privacy_tools',)
    actions = None

    @admin.display(description='Richieste privacy')
    def privacy_tools(self, obj):
        return format_html('<a href="{}">Gestisci una richiesta verificata</a>', reverse('otpadmin:privacy_member', args=[obj.pk]))

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('accountemail').prefetch_related(
            Prefetch('attempt_set', queryset=Attempt.objects.filter(finished=True).only('user_id', 'quiz', 'score'), to_attr='completed_attempts')
        )

    @admin.display(boolean=True, description='Email confermata')
    def email_verified(self, obj):
        return getattr(getattr(obj, 'accountemail', None), 'verified', False)

    def best_scores(self, obj):
        scores = {}
        for attempt in obj.completed_attempts:
            scores[attempt.quiz] = max(scores.get(attempt.quiz, 0), attempt.score)
        return scores

    @admin.display(description='Quiz completati')
    def completed_quizzes(self, obj):
        return len(self.best_scores(obj))

    @admin.display(description='Punteggio totale')
    def total_score(self, obj):
        return sum(self.best_scores(obj).values())

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Attempt, site=community_admin)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'quiz', 'score', 'finished', 'created')
    list_filter = ('finished', 'quiz', 'created')
    search_fields = ('user__username',)
    ordering = ('-created',)
    list_select_related = ('user',)
    fields = ('user', 'quiz', 'score', 'finished', 'created')
    readonly_fields = fields
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ReplyForm(forms.ModelForm):
    class Meta:
        model = PrivacyOperation
        fields = ['replied_on']

    def clean_replied_on(self):
        value = self.cleaned_data.get('replied_on')
        if value and (value > timezone.localdate() or value < self.instance.received_on):
            raise forms.ValidationError('Indica una data compresa tra ricezione e oggi.')
        return value


@admin.register(PrivacyOperation, site=community_admin)
class PrivacyOperationAdmin(admin.ModelAdmin):
    form = ReplyForm
    list_display = ('reference', 'action', 'received_on', 'due_on', 'performed_at', 'replied_on')
    list_filter = ('action', 'replied_on')
    ordering = ('-performed_at',)
    search_fields = ('reference',)
    fields = ('reference', 'subject', 'action', 'received_on', 'due_on', 'verification_method', 'verified_on', 'performed_at', 'result', 'receipt', 'replied_on')
    readonly_fields = fields[:-1]
    actions = None

    @admin.display(description='Scadenza del riscontro (un mese)')
    def due_on(self, obj):
        return next_month(obj.received_on)

    @admin.display(description='Ricevuta riservata')
    def receipt(self, obj):
        return format_html('<a href="{}">Scarica ricevuta e verifica dell’esito</a>', reverse('otpadmin:privacy_receipt', args=[obj.pk]))

    def has_module_permission(self, request):
        return permitted(request)

    def has_view_permission(self, request, obj=None):
        return permitted(request)

    def has_change_permission(self, request, obj=None):
        return permitted(request)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        # Restrict editing to the date of the actual reply, never the audit evidence.
        PrivacyOperation.objects.filter(pk=obj.pk).update(replied_on=form.cleaned_data['replied_on'])
