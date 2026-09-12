from datetime import datetime, timezone
from django.contrib.auth.models import User
from django.core import serializers
from django.test import TestCase
from ops.recovery_drill import serialize_snapshot


class RecoverySnapshotTests(TestCase):
    def test_snapshot_preserves_full_account_identity_timestamp(self):
        joined = datetime(2026, 9, 12, 21, 0, 0, 123456, tzinfo=timezone.utc)
        user = User.objects.create(username='synthetic-recovery', date_joined=joined)
        snapshot = serialize_snapshot([user])
        restored = list(serializers.deserialize('json', snapshot))[0].object
        self.assertEqual(restored.pk, user.pk)
        self.assertEqual(restored.date_joined, joined)
