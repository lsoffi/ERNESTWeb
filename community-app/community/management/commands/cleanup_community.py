import json
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from community.models import Attempt, RateBucket, AccountEmail
from community.retention import PROJECT_END, UNVERIFIED_TTL, GUEST_TTL, ANSWER_TTL


class Command(BaseCommand):
    help = 'Apply agreed retention deadlines; emit aggregate counts without personal data.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Report counts without deleting data.')

    def handle(self, *args, **options):
        now = timezone.now()
        ended = now >= PROJECT_END
        with transaction.atomic():
            # Use the same AccountEmail lock as verification: a confirmed account
            # must never be removed by a concurrent pending-account cleanup.
            pending = list(AccountEmail.objects.select_for_update().filter(
                verified=False, user__date_joined__lte=now-UNVERIFIED_TTL
            ).values_list('user_id', flat=True))
            users = User.objects.all() if ended else User.objects.filter(pk__in=pending)
            answers = Attempt.objects.filter(
                Q(finished=True) | Q(created__lte=now-ANSWER_TTL)
            ).exclude(answers=[])
            attempts = Attempt.objects.all() if ended else Attempt.objects.filter(
                user=None, created__lte=now-GUEST_TTL)
            rates = RateBucket.objects.all() if ended else RateBucket.objects.filter(
                window__lt=int(now.timestamp())//600-144)
            sessions = Session.objects.all() if ended else Session.objects.filter(expire_date__lte=now)
            report = dict(dry_run=options['dry_run'], project_ended=ended,
                          users=users.count(), answer_payloads=answers.count(),
                          attempts=attempts.count(), rate_buckets=rates.count(), sessions=sessions.count())
            if not options['dry_run']:
                answers.update(answers=[])
                attempts.delete()
                users.delete()  # Cascades to email records, results and OTP devices.
                rates.delete()
                sessions.delete()
        report['completed_at'] = now.isoformat()
        self.stdout.write(json.dumps(report, sort_keys=True))
