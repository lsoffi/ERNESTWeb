from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django_otp.plugins.otp_totp.models import TOTPDevice


class Command(BaseCommand):
    help = 'Revoke lost admin TOTP devices after an operator has verified identity.'

    def add_arguments(self, parser):
        parser.add_argument('nickname')

    def handle(self, *args, **options):
        user = User.objects.filter(username=options['nickname'], is_staff=True).first()
        if not user:
            raise CommandError('Administrator not found.')
        TOTPDevice.objects.filter(user=user).delete()
        self.stdout.write('Devices revoked. Admin access requires a new enrollment; no MFA bypass is enabled.')
