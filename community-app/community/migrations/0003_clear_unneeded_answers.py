from datetime import timedelta
from django.db import migrations
from django.db.models import Q
from django.utils import timezone


def clear_unneeded_answers(apps, schema_editor):
    Attempt = apps.get_model('community', 'Attempt')
    Attempt.objects.using(schema_editor.connection.alias).filter(
        Q(finished=True) | Q(created__lt=timezone.now() - timedelta(hours=2))
    ).exclude(answers=[]).update(answers=[])


class Migration(migrations.Migration):
    dependencies = [('community', '0002_accountemail')]
    operations = [migrations.RunPython(clear_unneeded_answers, migrations.RunPython.noop)]
