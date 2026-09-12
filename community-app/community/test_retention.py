import io
import json
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from community.models import AccountEmail, Attempt
from community.retention import PROJECT_END


class RetentionTests(TestCase):
    def account(self, name, age, verified=False):
        user = User.objects.create_user(name, email=name+'@example.org', date_joined=self.now-age)
        AccountEmail.objects.create(user=user, address=user.email, verified=verified)
        return user

    def setUp(self):
        self.now = timezone.now()

    def cleanup(self, **kwargs):
        out = io.StringIO()
        call_command('cleanup_community', stdout=out, **kwargs)
        return json.loads(out.getvalue())

    def test_deadlines_dry_run_and_idempotence(self):
        old = self.account('expired', timedelta(days=7))
        fresh = self.account('fresh', timedelta(days=7)-timedelta(seconds=1))
        verified = self.account('verified', timedelta(days=30), True)
        result = Attempt.objects.create(user=verified, session_key='', quiz='test', score=30, finished=True)
        guest = Attempt.objects.create(session_key='guest', quiz='test')
        Attempt.objects.filter(pk=guest.pk).update(created=self.now-timedelta(hours=24))
        with patch('community.management.commands.cleanup_community.timezone.now', return_value=self.now):
            report = self.cleanup(dry_run=True)
            self.assertEqual(report['users'], 1)
            self.assertTrue(User.objects.filter(pk=old.pk).exists())
            self.cleanup()
            self.assertFalse(User.objects.filter(pk=old.pk).exists())
            self.assertFalse(Attempt.objects.filter(pk=guest.pk).exists())
            self.assertTrue(User.objects.filter(pk__in=[fresh.pk, verified.pk]).count() == 2)
            result.refresh_from_db()
            self.assertEqual(result.score, 30)
            self.assertEqual(self.cleanup()['users'], 0)

    def test_project_end_clears_accounts_results_sessions_and_closes_api(self):
        user = self.account('registered', timedelta(days=1), True)
        Attempt.objects.create(user=user, session_key='', quiz='test', score=30, finished=True)
        Session.objects.create(session_key='test', session_data='', expire_date=PROJECT_END+timedelta(days=7))
        with patch('django.utils.timezone.now', return_value=PROJECT_END):
            self.assertEqual(self.client.post('/api/auth/register/', {}).status_code, 410)
            self.assertEqual(self.client.get('/api/state/').status_code, 410)
            report = self.cleanup()
            self.assertTrue(report['project_ended'])
            self.assertFalse(User.objects.exists())
            self.assertFalse(AccountEmail.objects.exists())
            self.assertFalse(Attempt.objects.exists())
            self.assertFalse(Session.objects.exists())

    def test_expired_pending_account_cannot_be_verified(self):
        from django.core import signing
        user = self.account('expired', timedelta(days=8))
        token = signing.dumps({'user': user.pk, 'email': user.email}, salt='ernest-verify')
        response = self.client.post('/account/verify/', {'token': token})
        self.assertFalse(response.context['valid'])
        user.accountemail.refresh_from_db()
        self.assertFalse(user.accountemail.verified)
