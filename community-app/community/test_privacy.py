import json
from datetime import timedelta
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core import signing
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice
from .models import AccountEmail, Attempt, PrivacyOperation
from .privacy import account_context, next_month
from .views import QUIZZES


@override_settings(PRIVACY_OPERATOR_USERNAME='operator')
class PrivacyTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_superuser('operator', email='operator@example.org', password='Strong-auth-782!')
        self.user = User.objects.create_user('member', email='member@example.org', password='Member-auth-492!')
        AccountEmail.objects.create(user=self.user, address=self.user.email, verified=True)
        self.other = User.objects.create_user('other', email='other@example.org')
        self.attempt = Attempt.objects.create(user=self.user, session_key='SECRET_SESSION', quiz=QUIZZES[0]['id'], score=30, finished=True)
        Attempt.objects.create(user=self.other, session_key='OTHER_SECRET', quiz=QUIZZES[1]['id'], score=10, finished=True)
        self.url = reverse('otpadmin:privacy_member', args=[self.user.pk])
        self.client.force_login(self.operator)
        self.device = TOTPDevice.objects.create(user=self.operator, confirmed=True)
        session = self.client.session
        session['otp_device_id'] = self.device.persistent_id
        session.save()

    def data(self, action='export', **extra):
        return {'account_token': signing.dumps(account_context(self.user), salt='privacy-account'),
                'reference': 'R-2026-001', 'received_on': str(timezone.localdate()),
                'verified_on': str(timezone.localdate()), 'verification_method': 'email',
                'evidence_checked': 'on', 'scope_checked': 'on',
                'confirm_username': self.user.username, 'action': action, **extra}

    def test_private_access_requires_designated_operator_and_otp(self):
        self.assertEqual(Client().get(self.url).status_code, 302)
        plain = Client(); plain.force_login(self.operator)
        self.assertEqual(plain.get(self.url).status_code, 302)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        with override_settings(PRIVACY_OPERATOR_USERNAME='another'):
            self.assertEqual(self.client.get(self.url).status_code, 403)
            self.assertEqual(self.client.get(reverse('otpadmin:community_privacyoperation_changelist')).status_code, 403)
        with override_settings(PRIVACY_OPERATOR_USERNAME=''):
            self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_export_is_scoped_and_excludes_secrets(self):
        response = self.client.post(self.url, self.data())
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment;', response['Content-Disposition'])
        payload = json.loads(response.content)
        self.assertEqual(payload['profilo']['email'], self.user.email)
        self.assertEqual(payload['punteggio_totale'], 30)
        self.assertEqual(len(payload['tentativi']), 1)
        text = response.content.decode()
        for secret in ['other@example.org', 'SECRET_SESSION', 'OTHER_SECRET', self.user.password, self.device.key]:
            self.assertNotIn(secret, text)
        self.assertEqual(PrivacyOperation.objects.count(), 1)
        self.assertIsNone(PrivacyOperation.objects.get().replied_on)
        self.assertIn('no-store', response['Cache-Control'])

    def test_missing_verification_and_stale_context_do_not_execute(self):
        self.client.post(self.url, self.data('delete', evidence_checked=''))
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        payload = self.data('delete')
        User.objects.filter(pk=self.user.pk).update(email='changed@example.org')
        self.client.post(self.url, payload)
        self.assertFalse(PrivacyOperation.objects.exists())
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_delete_checks_related_data_and_other_users_remain(self):
        member_client = Client(); member_client.force_login(self.user)
        session_key = member_client.session.session_key
        response = self.client.post(self.url, self.data('delete'))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(AccountEmail.objects.filter(user_id=self.user.pk).exists())
        self.assertFalse(Attempt.objects.filter(user_id=self.user.pk).exists())
        self.assertFalse(Session.objects.filter(pk=session_key).exists())
        self.assertTrue(User.objects.filter(pk=self.other.pk).exists())
        self.assertEqual(Attempt.objects.filter(user=self.other).count(), 1)
        op = PrivacyOperation.objects.get()
        self.assertTrue(op.result['verificato'])
        self.assertIsNone(op.subject)
        receipt = self.client.get(reverse('otpadmin:privacy_receipt', args=[op.pk]))
        self.assertEqual(receipt.status_code, 200)
        self.assertNotIn(self.user.email, receipt.content.decode())
        self.assertEqual(member_client.get('/api/leaderboard/').status_code, 401)

    def test_rectification_requires_new_email_verification_and_preserves_score(self):
        self.client.post(self.url, self.data('correct', new_email='new@example.org'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'member@example.org')
        response = self.client.post(self.url, self.data('correct', new_email='new@example.org', new_email_verified='on', new_username='newname'))
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'new@example.org')
        self.assertEqual(self.user.accountemail.address, 'new@example.org')
        self.assertEqual(self.user.username, 'newname')
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.score, 30)

    def test_duplicate_request_and_csrf_are_rejected(self):
        self.client.post(self.url, self.data())
        self.client.post(self.url, self.data('delete'))
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertEqual(PrivacyOperation.objects.count(), 1)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.cookies = self.client.cookies
        self.assertEqual(csrf_client.post(self.url, self.data('delete')).status_code, 403)

    def test_deadline_is_calendar_month(self):
        from datetime import date
        self.assertEqual(next_month(date(2026, 1, 31)), date(2026, 2, 28))
        self.assertEqual(next_month(date(2027, 12, 31)), date(2028, 1, 31))

    def test_signed_receipt_reapplies_only_original_account_after_restore(self):
        import io
        import tempfile
        from pathlib import Path
        from django.core.management import call_command, CommandError
        from .privacy import receipt_payload
        user_id, joined = self.user.pk, self.user.date_joined
        self.client.post(self.url, self.data('delete'))
        receipt = receipt_payload(PrivacyOperation.objects.get())
        User.objects.create(pk=user_id, username='restored', date_joined=joined)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'receipt.json'; path.write_text(json.dumps(receipt))
            call_command('reapply_privacy_deletions', str(path), stdout=io.StringIO())
            self.assertTrue(User.objects.filter(pk=user_id).exists())
            call_command('reapply_privacy_deletions', str(path), apply=True, stdout=io.StringIO())
            self.assertFalse(User.objects.filter(pk=user_id).exists())
            # A newly created account reusing an ID is not the deleted account.
            User.objects.create(pk=user_id, username='newaccount', date_joined=joined+timedelta(days=1))
            call_command('reapply_privacy_deletions', str(path), apply=True, stdout=io.StringIO())
            self.assertTrue(User.objects.filter(pk=user_id).exists())
            receipt['proof'] += 'tampered'; path.write_text(json.dumps(receipt))
            with self.assertRaises(CommandError):
                call_command('reapply_privacy_deletions', str(path), apply=True, stdout=io.StringIO())
