"""Reapply signed deletion receipts after a database restore, before reopening."""
import json
from datetime import datetime
from pathlib import Path
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core import signing
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from community.models import AccountEmail, Attempt
from community.privacy import sessions_for


class Command(BaseCommand):
    help = 'Verify signed privacy deletion receipts; dry run unless --apply is specified.'

    def add_arguments(self, parser):
        parser.add_argument('receipts', nargs='+')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        targets = set()
        # Validate every input before making any change; ignore editable outer fields.
        for filename in options['receipts']:
            try:
                raw = Path(filename).read_bytes()
                if len(raw) > 65536: raise ValueError('Oversized receipt')
                payload = signing.loads(json.loads(raw)['proof'], salt='ernest-privacy-receipt')
                if payload['azione'] != 'delete' or payload['esito']['verificato'] is not True:
                    raise ValueError('Not a successful deletion receipt')
                joined = datetime.fromisoformat(payload['account_creato_il'])
                if joined.tzinfo is None or type(payload['account_id']) is not int: raise ValueError()
                targets.add((payload['account_id'], joined))
            except (OSError, ValueError, KeyError, TypeError, signing.BadSignature):
                raise CommandError('Ricevuta assente, non valida o non firmata da questa applicazione; nessuna modifica eseguita.') from None
        matched = 0
        with transaction.atomic():
            for user_id, joined in sorted(targets):
                list(AccountEmail.objects.select_for_update().filter(user_id=user_id))
                user = User.objects.select_for_update().filter(pk=user_id, date_joined=joined).first()
                if user is None: continue
                if user.is_staff or user.is_superuser:
                    raise CommandError('Account amministrativo rilevato: operazione annullata.')
                matched += 1
                if options['apply']:
                    Session.objects.filter(pk__in=[s.pk for s in sessions_for(user)]).delete()
                    user.delete()
                    if User.objects.filter(pk=user_id).exists() or Attempt.objects.filter(user_id=user_id).exists():
                        raise CommandError('Controllo finale fallito: operazione annullata.')
        self.stdout.write(json.dumps({'dry_run': not options['apply'], 'accounts_matched': matched, 'verified_receipts': len(targets)}))
