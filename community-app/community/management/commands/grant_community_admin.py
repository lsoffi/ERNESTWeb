from django.contrib.auth.models import User, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = 'Grant member monitoring permissions to an existing verified account.'

    def add_arguments(self, parser):
        parser.add_argument('nickname')

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            user = User.objects.select_for_update().get(username=options['nickname'].strip().lower())
        except User.DoesNotExist:
            raise CommandError('Account not found; register and verify it first.')
        if not user.is_active or not getattr(getattr(user, 'accountemail', None), 'verified', False):
            raise CommandError('Account must be active with a verified email.')
        user.is_staff = True
        user.save(update_fields=['is_staff'])
        for app, model, codes in [('auth', 'user', ['view_user', 'change_user']), ('community', 'attempt', ['view_attempt'])]:
            permissions = Permission.objects.filter(content_type__app_label=app, content_type__model=model, codename__in=codes)
            if permissions.count() != len(codes):
                raise CommandError('Run migrations before granting permissions.')
            user.user_permissions.add(*permissions)
        self.stdout.write(self.style.SUCCESS('Community monitoring access enabled for the requested verified account.'))
