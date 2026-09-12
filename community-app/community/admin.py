from django.contrib import admin
from django_otp.admin import OTPAdminSite
from django.contrib.auth.models import User
from django.db.models import Prefetch
from django.http import HttpResponse
from .models import Attempt


class CommunityAdminSite(OTPAdminSite):
    site_header = 'ERNEST — Gestione community'
    site_title = 'ERNEST amministrazione'
    index_title = 'Iscritti e risultati'
    site_url = '/'

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
    readonly_fields = fields[:-1]
    actions = None

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
