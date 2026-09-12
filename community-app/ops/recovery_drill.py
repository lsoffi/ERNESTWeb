"""Run only in a disposable CERN DBOD clone, with no public route or SMTP secret.

The expected endpoint must be copied from the clone's DBOD page. Never point this
script at the live instance. Output contains checks/timings, never account data.
"""
import hashlib
import io
import json
import os
import re
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.request


def guard():
    endpoint = (os.environ.get('MYSQL_HOST'), os.environ.get('MYSQL_PORT'))
    expected = (os.environ.get('RECOVERY_EXPECTED_HOST'), os.environ.get('RECOVERY_EXPECTED_PORT'))
    if os.environ.get('RECOVERY_DRILL') != '1' or not all(expected) or endpoint != expected:
        raise RuntimeError('Isolated recovery endpoint must be explicitly configured')
    if not re.fullmatch(r'dbod-ernest-community-clone-[0-9]{14}\.cern\.ch', endpoint[0]) or endpoint[1] == '5557':

        raise RuntimeError('Production recovery drill is forbidden')
    if os.environ.get('EMAIL_HOST_PASSWORD'):
        raise RuntimeError('Do not mount the SMTP secret in a recovery drill')


def serialize_snapshot(objects):
    # Django's default JSON encoder truncates datetimes to milliseconds. A
    # recovery snapshot must preserve the exact identity timestamp used by the
    # signed deletion receipt, as a native MySQL backup does.
    from datetime import datetime
    from django.core import serializers
    from django.core.serializers.json import DjangoJSONEncoder

    class ExactDateTimeEncoder(DjangoJSONEncoder):
        def default(self, value):
            if isinstance(value, datetime):
                return value.isoformat()
            return super().default(value)

    return serializers.serialize('json', objects, cls=ExactDateTimeEncoder)


STAGE = 'guard'

def run():
    global STAGE
    guard()
    sys.path.insert(0, '/opt/app-root/src')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    STAGE = 'django_setup'
    import django
    django.setup()
    from django.conf import settings
    from django.contrib.auth.models import User
    from django.contrib.sessions.models import Session
    from django.core import serializers
    from django.core.management import call_command
    from django.db import connection
    from django.test import Client, override_settings
    from django.utils import timezone
    from community.models import AccountEmail, Attempt, PrivacyOperation
    from community.privacy import receipt_payload
    from community.views import QUIZZES
    report = {'checks': {}, 'durations_seconds': {}}
    STAGE = 'clone_connection_tls'
    with connection.cursor() as cursor:
        cursor.execute('SELECT VERSION(), @@port')
        version, server_port = cursor.fetchone()
        assert str(server_port) == os.environ['RECOVERY_EXPECTED_PORT']
        cursor.execute("SHOW SESSION STATUS LIKE 'Ssl_cipher'")
        assert cursor.fetchone()[1], 'Database connection must use TLS'
    report['mysql_version'] = version
    report['checks']['clone_endpoint_and_tls'] = True

    def progress_digest():
        rows = list(Attempt.objects.filter(user__accountemail__verified=True, finished=True)
                    .order_by('pk').values_list('pk', 'user_id', 'quiz', 'score', 'finished'))
        return hashlib.sha256(json.dumps(rows, default=str).encode()).digest()

    STAGE = 'restored_progress'
    before = progress_digest()
    started = time.monotonic()
    STAGE = 'migrate_clone'
    call_command('migrate', interactive=False, stdout=io.StringIO(), verbosity=0)
    assert before == progress_digest()
    STAGE = 'retention_clone'
    call_command('cleanup_community', stdout=io.StringIO())
    assert before == progress_digest()
    report['checks']['backup_migrates_and_preserves_registered_results'] = True
    report['durations_seconds']['migrate_and_retention'] = round(time.monotonic()-started, 3)

    with tempfile.TemporaryDirectory(prefix='ernest-recovery-') as work:
        work = Path(work)
        # The child process has no SMTP credentials and serves loopback only.
        env = {**os.environ, 'DJANGO_ALLOWED_HOSTS': 'localhost,127.0.0.1,testserver',
               'TRUST_PROXY': '1', 'EMAIL_HOST': '', 'EMAIL_HOST_USER': '',
               'EMAIL_HOST_PASSWORD': '', 'PUBLIC_BASE_URL': 'https://localhost'}
        for cycle in (1, 2):
            STAGE = f'app_start_{cycle}'
            started = time.monotonic()
            with (work/'gunicorn.log').open('w') as log:
                process = subprocess.Popen([sys.executable, '-m', 'gunicorn', '--bind', '127.0.0.1:18080',
                    '--workers', '1', '--access-logfile', '/dev/null', 'config.wsgi:application'],
                    cwd='/opt/app-root/src', env=env, stdout=log, stderr=log)
                try:
                    for _ in range(100):
                        if process.poll() is not None: raise RuntimeError('Recovered application failed to start')
                        try:
                            request = urllib.request.Request('http://127.0.0.1:18080/api/state/', headers={'X-Forwarded-Proto': 'https'})
                            with urllib.request.urlopen(request, timeout=2) as response:
                                state = json.load(response)
                                assert response.status == 200 and len(state['quizzes']) == len(QUIZZES)
                            break
                        except OSError:
                            time.sleep(.2)
                    else: raise RuntimeError('Recovered application did not become ready')
                finally:
                    process.terminate()
                    try: process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait()
            assert before == progress_digest()
            report['durations_seconds'][f'app_start_{cycle}'] = round(time.monotonic()-started, 3)
        report['checks']['fresh_app_and_restart_preserve_database'] = True

        STAGE = 'synthetic_account'
        name = 'drill_' + secrets.token_hex(5)
        password = secrets.token_urlsafe(24)
        user = User.objects.create_user(name, email=name+'@example.invalid', password=password)
        AccountEmail.objects.create(user=user, address=user.email, verified=True)
        user_id = user.pk
        try:
            with override_settings(EMAIL_BACKEND='django.core.mail.backends.dummy.EmailBackend',
                    ALLOWED_HOSTS=['testserver'], CSRF_TRUSTED_ORIGINS=['https://testserver'], ACCOUNTS_ENABLED=True):
                client = Client(enforce_csrf_checks=True)
                client.get('/', secure=True)
                def post(path, data):
                    return client.post(path, json.dumps(data), content_type='application/json', secure=True,
                        HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value, HTTP_ORIGIN='https://testserver')
                STAGE = 'synthetic_login'
                assert post('/api/auth/login/', {'email':user.email, 'password':password}).status_code == 200
                STAGE = 'synthetic_quiz'
                quiz = QUIZZES[0]
                response = post('/api/start/', {'quiz':quiz['id']})
                assert response.status_code == 200
                attempt_id = response.json()['attempt']
                for index, question in enumerate(quiz['questions']):
                    response = post('/api/answer/', {'attempt':attempt_id, 'index':index, 'answer':question[2]})
                    assert response.status_code == 200
                assert response.json()['finished'] and response.json()['score'] == 30
                state = client.get('/api/state/', secure=True).json()
                assert state['completed'][quiz['id']] == 30 and any(x['earned'] for x in state['passport'])
                assert Attempt.objects.get(pk=attempt_id).answers == []
                report['checks']['restored_app_login_quiz_score_stamp'] = True

                # A synthetic-only logical backup from before a deletion. Real
                # participant data never leaves the clone or appears in this file.
                STAGE = 'synthetic_backup'
                snapshot = serialize_snapshot([user, user.accountemail,
                    *Attempt.objects.filter(user=user), Session.objects.get(pk=client.session.session_key)])
                operation = PrivacyOperation.objects.create(reference=name, subject=user,
                    subject_id_at_request=user.pk, subject_joined_at=user.date_joined,
                    received_on=timezone.localdate(), verified_on=timezone.localdate(),
                    verification_method='authenticated', action='delete', result={'verificato': True})
                receipt = work/'deletion.json'
                receipt.write_text(json.dumps(receipt_payload(operation)))
                receipt.chmod(0o600)
                Session.objects.filter(pk=client.session.session_key).delete()
                user.delete()
                assert not User.objects.filter(pk=user_id).exists()
                # Reintroduce only the synthetic account from its older backup.
                STAGE = 'synthetic_restore'
                for obj in serializers.deserialize('json', snapshot): obj.save()
                assert User.objects.filter(pk=user_id, date_joined=operation.subject_joined_at).exists()
                STAGE = 'deletion_replay'
                call_command('reapply_privacy_deletions', str(receipt), stdout=io.StringIO())
                assert User.objects.filter(pk=user_id).exists()
                STAGE = 'deletion_apply'
                call_command('reapply_privacy_deletions', str(receipt), apply=True, stdout=io.StringIO())
                STAGE = 'deletion_repeat'
                call_command('reapply_privacy_deletions', str(receipt), apply=True, stdout=io.StringIO())
                STAGE = 'deletion_readback'
                assert not User.objects.filter(pk=user_id).exists()
                assert not AccountEmail.objects.filter(user_id=user_id).exists()
                assert not Attempt.objects.filter(user_id=user_id).exists()
                assert not Session.objects.filter(pk=client.session.session_key).exists()
                report['checks']['old_snapshot_deletion_reapplied_and_idempotent'] = True
                assert before == progress_digest()
                report['checks']['other_registered_results_unchanged'] = True
        finally:
            # All mutations are in the disposable clone, subsequently expired.
            User.objects.filter(pk=user_id).delete()
            PrivacyOperation.objects.filter(reference=name).delete()
    report['completed_at'] = timezone.now().isoformat()
    report['checks']['smtp_disabled_no_public_route'] = True
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    try:
        run()
    except Exception as exc:
        # Never put DB connection details, account data, or credentials in logs.
        print(json.dumps({'recovery_check': 'failed', 'error_type': type(exc).__name__, 'stage': STAGE}))
        raise SystemExit(1)
