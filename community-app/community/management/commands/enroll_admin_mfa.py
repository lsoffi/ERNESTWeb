"""Provision a TOTP device through an authenticated operator terminal only."""
import getpass
import os
from pathlib import Path
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django_otp.plugins.otp_totp.models import TOTPDevice


class Command(BaseCommand):
    help = 'Enroll an existing verified administrator in TOTP; never prints a secret.'

    def add_arguments(self, parser):
        parser.add_argument('nickname')
        parser.add_argument('--provisioning-file', required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        user = User.objects.select_for_update().filter(username=options['nickname'], is_active=True, is_staff=True, accountemail__verified=True).first()
        if user is None:
            raise CommandError('A verified active staff account is required.')
        if TOTPDevice.objects.filter(user=user, confirmed=True).exists():
            raise CommandError('An MFA device already exists. Use the documented recovery procedure.')
        path = Path(options['provisioning_file'])
        if not path.is_absolute():
            raise CommandError('Use an absolute path outside the repository and web directories.')
        from django.conf import settings
        if path.resolve().is_relative_to(settings.BASE_DIR.resolve()):
            raise CommandError('Provisioning files must be outside the application directory.')
        device = TOTPDevice.objects.create(user=user, name='ERNEST admin', confirmed=False)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except OSError:
            raise CommandError('Cannot create a new private provisioning file.')
        try:
            with os.fdopen(fd, 'w') as output:
                output.write(device.config_url + '\n')
            self.stdout.write('Import the private provisioning file into your authenticator. Do not share it or copy it into logs/chat.')
            token = getpass.getpass('Authenticator code: ')
            if not device.verify_token(token):
                raise CommandError('Invalid code; enrollment was not saved. Run enrollment again.')
            device.confirmed = True
            device.save(update_fields=['confirmed'])
        finally:
            path.unlink(missing_ok=True)
        self.stdout.write(self.style.SUCCESS('MFA enrolled. The provisioning file has been removed.'))
