import io
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.db import close_old_connections, connection
from django.test import Client, RequestFactory, TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice
from .models import AccountEmail, Attempt, RateBucket
from .security import client_address, limited
from .safe_logging import SafeFormatter


@override_settings(ACCOUNTS_ENABLED=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class SecurityTests(TestCase):
    def post(self, path, data, **extra):
        return self.client.post('/api/'+path+'/',json.dumps(data),content_type='application/json',**extra)

    def test_registration_response_does_not_disclose_existing_email_or_nickname(self):
        data={'email':'private@example.org','username':'privateuser','password':'Cosmic-data-453!','password2':'Cosmic-data-453!'}
        first=self.post('auth/register',data)
        for changed in [data,{**data,'username':'newnickname'},{**data,'email':'another@example.org'}]:
            response=self.post('auth/register',changed)
            self.assertEqual(response.status_code,first.status_code)
            self.assertEqual(response.json(),first.json())
            self.assertNotIn('preview_url',response.json())
        self.assertEqual(User.objects.count(),1)
        self.assertEqual(len(mail.outbox),1)
        self.assertFalse(User.objects.get().is_active)

    def test_mail_failure_uses_same_generic_registration_response(self):
        data={'email':'private@example.org','username':'privateuser','password':'Cosmic-data-453!','password2':'Cosmic-data-453!'}
        with patch('community.views.deliver',side_effect=RuntimeError('smtp-password-secret')):
            first=self.post('auth/register',data)
        second=self.post('auth/register',data)
        self.assertEqual(first.json(),second.json())
        self.assertNotIn('smtp',first.content.decode())

    def test_untrusted_forwarded_header_cannot_bypass_auth_limit(self):
        for i in range(11):
            response=self.client.post('/admin/login/',{'username':'x','password':'bad'},HTTP_X_FORWARDED_FOR=f'198.51.100.{i}')
        self.assertEqual(response.status_code,429)
        self.assertIn('Retry-After',response)
        for bucket in RateBucket.objects.all():
            self.assertNotIn('127.0.0.1',bucket.key)

    @override_settings(TRUSTED_PROXY_CIDRS=['10.2.0.0/16'])
    def test_proxy_chain_uses_rightmost_untrusted_address(self):
        factory=RequestFactory()
        request=factory.get('/',REMOTE_ADDR='10.2.1.4',HTTP_X_FORWARDED_FOR='1.2.3.4, 198.51.100.9, 10.2.1.3')
        self.assertEqual(client_address(request),'198.51.100.9')
        request.META['REMOTE_ADDR']='192.0.2.1'
        self.assertEqual(client_address(request),'192.0.2.1')
        request.META['REMOTE_ADDR']='10.2.1.4'
        request.META['HTTP_X_FORWARDED_FOR']='garbage'
        self.assertEqual(client_address(request),'10.2.1.4')

    def test_large_request_is_rejected_without_data_write(self):
        response=self.post('auth/register',{'email':'x'*9000})
        self.assertEqual(response.status_code,413)
        self.assertFalse(User.objects.exists())

    def test_guest_session_rotation_does_not_reset_ip_budget(self):
        for _ in range(120):
            limited('quiz-start-ip:127.0.0.1',120)
        for _ in range(2):
            response=Client().post('/api/start/',json.dumps({'quiz':'luce'}),content_type='application/json')
            self.assertEqual(response.status_code,429)
        self.assertFalse(Attempt.objects.exists())

    def test_sessions_are_isolated_and_deactivated_user_loses_access(self):
        owner=User.objects.create_user('owner',password='Cosmic-waves-782!')
        other=User.objects.create_user('other',password='Cosmic-waves-731!')
        attempt=Attempt.objects.create(user=owner,quiz='luce',session_key='test')
        self.client.force_login(other)
        self.assertEqual(self.post('answer',{'attempt':str(attempt.pk),'index':0,'answer':0}).status_code,404)
        self.client.force_login(owner)
        owner.is_active=False;owner.save()
        self.assertEqual(self.client.get('/api/leaderboard/').status_code,401)
        self.assertEqual(self.post('answer',{'attempt':str(attempt.pk),'index':0,'answer':0}).status_code,404)

    def test_registration_validation_still_rejects_invalid_passwords(self):
        data={'email':'a@example.org','username':'alice','password':'123','password2':'123'}
        self.assertEqual(self.post('auth/register',data).status_code,400)
        self.assertFalse(User.objects.exists())

    def test_admin_requires_otp_even_after_public_login(self):
        admin=User.objects.create_superuser('admin',email='admin@example.org',password='Strong-auth-782!')
        AccountEmail.objects.create(user=admin,address=admin.email,verified=True)
        self.post('auth/login',{'email':admin.email,'password':'Strong-auth-782!'})
        self.assertEqual(self.client.get('/admin/').status_code,302)
        self.assertEqual(self.client.get('/admin/auth/user/').status_code,302)
        response=self.client.post('/admin/login/',{'username':'admin','password':'Strong-auth-782!'})
        self.assertNotEqual(response.status_code,302)

    def test_totp_login_rejects_wrong_and_replayed_tokens_and_revoked_device(self):
        admin=User.objects.create_superuser('admin',password='Strong-auth-782!')
        device=TOTPDevice.objects.create(user=admin,confirmed=True)
        data={'username':'admin','password':'Strong-auth-782!','otp_device':device.persistent_id,'otp_token':'not-a-token'}
        self.assertEqual(self.client.post('/admin/login/',data).status_code,200)
        device.refresh_from_db();device.throttle_reset()
        code=totp(device.bin_key,step=device.step,t0=device.t0,digits=device.digits)
        data['otp_token']=str(code).zfill(device.digits)
        self.assertEqual(self.client.post('/admin/login/',data).status_code,302)
        self.assertLessEqual(self.client.session.get_expiry_age(),1800)
        self.assertEqual(self.client.get('/admin/').status_code,200)
        self.assertEqual(Client().post('/admin/login/',data).status_code,200)
        device.delete()
        self.assertEqual(self.client.get('/admin/').status_code,302)

    def test_application_logs_drop_sensitive_messages_and_tracebacks(self):
        record=logging.LogRecord('django.request',logging.ERROR,'',0,'https://host/?token=private-token email@example.org password=secret',(),None)
        try: raise RuntimeError('secret inside exception')
        except RuntimeError:
            import sys
            record.exc_info=sys.exc_info()
        result=SafeFormatter().format(record)
        for value in ['token','example.org','secret','Traceback']:
            self.assertNotIn(value,result)

    def test_gunicorn_access_logs_do_not_contain_query_headers_or_user_ids(self):
        spec=spec_from_file_location('test_gunicorn_config',Path(settings.BASE_DIR)/'gunicorn.conf.py')
        module=module_from_spec(spec);spec.loader.exec_module(module)
        logger=object.__new__(module.PrivateLogger)
        stream=io.StringIO();logger.access_log=logging.getLogger('test-access')
        logger.access_log.handlers=[logging.StreamHandler(stream)];logger.access_log.setLevel(logging.INFO);logger.access_log.propagate=False
        env={'PATH_INFO':'/account/verify/','QUERY_STRING':'token=private-token','HTTP_REFERER':'secret','HTTP_AUTHORIZATION':'Bearer secret'}
        logger.access(SimpleNamespace(status='200 OK'),None,env,timedelta(milliseconds=5))
        value=stream.getvalue()
        self.assertEqual(json.loads(value)['route'],'account')
        self.assertNotIn('secret',value);self.assertNotIn('token',value)


class MySQLConcurrencyTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_one_answer_cannot_be_awarded_twice_concurrently(self):
        user=User.objects.create_user('parallel',password='Strong-parallel-729!')
        attempt=Attempt.objects.create(user=user,quiz='luce',session_key='parallel')
        clients=[Client(),Client()]
        for client in clients: client.force_login(user)
        barrier=Barrier(2)
        def submit(client):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return client.post('/api/answer/',json.dumps({'attempt':str(attempt.pk),'index':0,'answer':0,'score':999}),content_type='application/json').status_code
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses=list(pool.map(submit,clients))
        self.assertEqual(sorted(statuses),[200,409])
        attempt.refresh_from_db();self.assertEqual(attempt.score,10);self.assertEqual(len(attempt.answers),1)

    @skipUnlessDBFeature('has_select_for_update')
    def test_simultaneous_rate_counter_updates_are_not_lost(self):
        limited('parallel-budget',10)
        def increment(_):
            close_old_connections()
            try: return limited('parallel-budget',10)
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=4) as pool:
            result=list(pool.map(increment,range(12)))
        self.assertEqual(sum(result),3)


class MFAEnrollmentTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('operator', is_staff=True)
        AccountEmail.objects.create(user=self.admin, address='operator@example.org', verified=True)

    def test_enrollment_file_is_private_removed_and_secret_not_logged(self):
        import tempfile
        from django.core.management import call_command
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'provisioning'
            output = io.StringIO()
            def token(prompt):
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertTrue(path.read_text().startswith('otpauth://'))
                device = TOTPDevice.objects.get(user=self.admin)
                return str(totp(device.bin_key, step=device.step, t0=device.t0, digits=device.digits))
            with patch('community.management.commands.enroll_admin_mfa.getpass.getpass', side_effect=token):
                call_command('enroll_admin_mfa', 'operator', provisioning_file=str(path), stdout=output)
            self.assertFalse(path.exists())
            self.assertTrue(TOTPDevice.objects.get(user=self.admin).confirmed)
            self.assertNotIn('otpauth://', output.getvalue())
            self.assertNotIn(TOTPDevice.objects.get(user=self.admin).key, output.getvalue())

    def test_bad_code_rolls_back_enrollment_and_removes_file(self):
        import tempfile
        from django.core.management import call_command, CommandError
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'provisioning'
            with patch('community.management.commands.enroll_admin_mfa.getpass.getpass', return_value='not-a-code'):
                with self.assertRaises(CommandError):
                    call_command('enroll_admin_mfa', 'operator', provisioning_file=str(path), stdout=io.StringIO())
            self.assertFalse(path.exists())
            self.assertFalse(TOTPDevice.objects.exists())

    def test_enrollment_never_overwrites_an_existing_file(self):
        import tempfile
        from django.core.management import call_command, CommandError
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'existing'
            path.write_text('keep me')
            with self.assertRaises(CommandError):
                call_command('enroll_admin_mfa', 'operator', provisioning_file=str(path), stdout=io.StringIO())
            self.assertEqual(path.read_text(), 'keep me')
            self.assertFalse(TOTPDevice.objects.exists())
