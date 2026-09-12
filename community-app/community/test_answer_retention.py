import importlib
import json
from datetime import timedelta
from types import SimpleNamespace
from django.apps import apps
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.utils import timezone
from .models import Attempt, AccountEmail
from .views import QUIZ_MAP


class AnswerRetentionTests(TestCase):
    def test_completion_discards_answers_but_keeps_score_stamp_and_replay_guard(self):
        user = User.objects.create_user('retention')
        AccountEmail.objects.create(user=user, address='retention@example.org', verified=True)
        self.client.force_login(user)
        result = self.client.post('/api/start/', json.dumps({'quiz': 'luce'}), content_type='application/json')
        pk = result.json()['attempt']
        for i, question in enumerate(QUIZ_MAP['luce']['questions']):
            result = self.client.post('/api/answer/', json.dumps({'attempt': pk, 'index': i, 'answer': question[2]}), content_type='application/json')
            self.assertEqual(result.status_code, 200)
        attempt = Attempt.objects.get(pk=pk)
        self.assertEqual(attempt.answers, [])
        self.assertTrue(attempt.finished)
        self.assertEqual(attempt.score, 30)
        self.assertEqual(result.json()['completed']['luce'], 30)
        self.assertTrue(next(s for s in result.json()['passport'] if s['id'] == 'idea')['earned'])
        self.assertEqual(self.client.get('/api/leaderboard/').json()['mine']['score'], 30)
        replay = self.client.post('/api/answer/', json.dumps({'attempt': pk, 'index': 0, 'answer': 0}), content_type='application/json')
        self.assertEqual(replay.status_code, 409)
        attempt.refresh_from_db()
        self.assertEqual(attempt.score, 30)

    def old_attempts(self):
        user = User.objects.create_user('history')
        done = Attempt.objects.create(user=user, quiz='luce', finished=True, score=20, answers=[0, 1, 2])
        expired = Attempt.objects.create(user=user, quiz='luce', score=10, answers=[0])
        Attempt.objects.filter(pk=expired.pk).update(created=timezone.now()-timedelta(hours=3))
        active = Attempt.objects.create(quiz='luce', session_key='active', score=10, answers=[0])
        return done, expired, active

    def assert_cleaned(self, attempts):
        done, expired, active = attempts
        for obj in attempts:
            obj.refresh_from_db()
        self.assertEqual(done.answers, [])
        self.assertEqual((done.score, done.finished), (20, True))
        self.assertEqual(expired.answers, [])
        self.assertEqual((expired.score, expired.finished), (10, False))
        self.assertEqual(active.answers, [0])

    def test_migration_cleans_history_without_changing_results_or_live_quizzes(self):
        attempts = self.old_attempts()
        migrate = importlib.import_module('community.migrations.0003_clear_unneeded_answers').clear_unneeded_answers
        for _ in range(2):
            migrate(apps, SimpleNamespace(connection=connection))
        self.assert_cleaned(attempts)

    def test_recurring_cleanup_removes_expired_answers_from_registered_accounts(self):
        attempts = self.old_attempts()
        call_command('cleanup_community', verbosity=0)
        self.assert_cleaned(attempts)
