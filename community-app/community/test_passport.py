from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase
from .models import Attempt
from .views import passport_for, PASSPORT, QUIZZES


class PassportTests(TestCase):
    def test_mapping_is_valid_and_zero_score_earns_stamp(self):
        ids = {icon['id'] for icon in PASSPORT}
        self.assertEqual(len(ids), 6)
        self.assertTrue(all(q['stamp'] in ids for q in QUIZZES))
        self.assertEqual({q['stamp'] for q in QUIZZES}, ids)
        self.assertEqual(sum(s['earned'] for s in passport_for({q['id']: 0 for q in QUIZZES})), 6)
        earned = [s['id'] for s in passport_for({'luce': 0}) if s['earned']]
        self.assertEqual(earned, ['idea'])

    def test_existing_results_count_partial_attempts_do_not_and_users_are_isolated(self):
        user = User.objects.create_user('passport-owner')
        other = User.objects.create_user('passport-other')
        Attempt.objects.create(user=user, quiz='luce', finished=True, score=0)
        Attempt.objects.create(user=user, quiz='luce', finished=True, score=20)
        Attempt.objects.create(user=user, quiz='indizi', finished=False, score=10)
        Attempt.objects.create(user=other, quiz='particelle', finished=True, score=30)
        self.client.force_login(user)
        stamps = self.client.get('/api/state/').json()['passport']
        self.assertEqual([s['id'] for s in stamps if s['earned']], ['idea'])

    def test_multiple_quizzes_for_one_icon_still_give_one_stamp(self):
        quizzes = [{**q, 'stamp': 'idea'} for q in QUIZZES]
        with patch('community.views.QUIZZES', quizzes):
            self.assertEqual(sum(s['earned'] for s in passport_for({'luce': 0, 'particelle': 30})), 1)

    def test_guest_passport_follows_only_its_session(self):
        session = self.client.session
        session.save()
        Attempt.objects.create(quiz='indizi', session_key=session.session_key, finished=True, score=0)
        Attempt.objects.create(quiz='luce', session_key='another-session', finished=True, score=30)
        stamps = self.client.get('/api/state/').json()['passport']
        self.assertEqual([s['id'] for s in stamps if s['earned']], ['observe'])

    def test_passport_labels_and_book_controls_are_translated(self):
        from .i18n import CATALOGS
        controls = ['ERNEST / IL MIO PASSAPORTO', 'Ogni scoperta lascia un segno.',
                    'Il tuo viaggio nella scienza, una pagina alla volta.',
                    'Passaporto online', 'Apri il tuo passaporto', '← Chiudi il passaporto',
                    'Tocca la copertina per sfogliare il passaporto.',
                    'Suono della pagina: attivo', 'Suono della pagina: disattivato',
                    'PASSAPORTO ONLINE', 'PASSAPORTO DI', 'Timbri raccolti',
                    'Esploratore ospite', 'Timbro conquistato', 'Da conquistare']
        for language in ('en', 'fr'):
            for label in [icon['label'] for icon in PASSPORT] + controls:
                self.assertTrue(CATALOGS[language].get(label), (language, label))
