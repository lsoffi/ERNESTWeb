import time
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone
from community.models import Attempt, RateBucket

class Command(BaseCommand):
    help = 'Remove anonymous attempts older than one day, old rate buckets and expired sessions.'
    def handle(self, *args, **options):
        Attempt.objects.filter(user=None, created__lt=timezone.now()-timedelta(days=1)).delete()
        RateBucket.objects.filter(window__lt=int(time.time())//600-144).delete()
        call_command('clearsessions')
        self.stdout.write('Cleanup completed.')
