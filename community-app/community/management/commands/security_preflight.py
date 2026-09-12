from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.contrib.auth.models import User
from django_otp.plugins.otp_totp.models import TOTPDevice


class Command(BaseCommand):
    help = 'Read-only production checks; never outputs credentials or grants.'

    def add_arguments(self, parser):
        parser.add_argument('--database', action='store_true')

    def handle(self, *args, **options):
        failures = []
        if settings.DEBUG:
            failures.append('DEBUG must be disabled')
        if not (settings.SESSION_COOKIE_SECURE and settings.CSRF_COOKIE_SECURE and settings.SECURE_SSL_REDIRECT):
            failures.append('HTTPS/cookie settings must be enabled')
        if not settings.PUBLIC_BASE_URL.startswith('https://'):
            failures.append('PUBLIC_BASE_URL must use HTTPS')
        database = settings.DATABASES['default']
        if database['ENGINE'] != 'django.db.backends.mysql' or database.get('OPTIONS', {}).get('ssl_mode') != 'VERIFY_IDENTITY':
            failures.append('Production requires MySQL with certificate identity verification')
        if database.get('USER', '').lower() in ('root', 'admin'):
            failures.append('Use a dedicated application database user')
        if options['database']:
            if connection.vendor != 'mysql':
                failures.append('Database verification requires MySQL')
            else:
                with connection.cursor() as cursor:
                    cursor.execute("SHOW SESSION STATUS LIKE 'Ssl_cipher'")
                    row = cursor.fetchone()
                    if not row or not row[1]: failures.append('Database session is not encrypted')
                    cursor.execute('SHOW GRANTS FOR CURRENT_USER()')
                    for row in cursor.fetchall():
                        grant = row[0].upper()
                        if (' ON *.* ' in grant and not grant.startswith('GRANT USAGE ')) or 'WITH GRANT OPTION' in grant:
                            failures.append('Application database user has excessive direct privileges')
                            break
            admins = User.objects.filter(is_staff=True, is_active=True)
            if not admins.exists(): failures.append('No active administrator')
            for admin in admins:
                if not TOTPDevice.objects.filter(user=admin, confirmed=True).exists():
                    failures.append('An administrator is missing a confirmed MFA device')
                    break
        if failures:
            raise CommandError('; '.join(failures))
        self.stdout.write('Configured checks passed. Network policy, inherited database roles and infrastructure logs still require operator review.')
