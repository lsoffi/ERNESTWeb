import json
from django.test import TestCase, Client, override_settings
from django.core import mail
from urllib.parse import urlsplit, parse_qs
from unittest.mock import patch
from django.contrib.auth.models import User
from .models import Attempt

@override_settings(ACCOUNTS_ENABLED=True, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class CommunityTests(TestCase):
    def post(self, path, data, client=None):
        return (client or self.client).post('/api/'+path+'/', json.dumps(data), content_type='application/json')
    def register(self, name='explorer'):
        result = self.post('auth/register', {'email': name+'@example.org', 'username': name, 'password': 'Test-cosmic-239!', 'password2': 'Test-cosmic-239!'})
        if mail.outbox and 'Controlla la posta' in result.json().get('message',''):
            url = mail.outbox[-1].body.splitlines()[-1]
            token = parse_qs(urlsplit(url).query)['token'][0]
            self.client.post('/account/verify/', {'token':token})
            self.post('auth/login', {'email':name+'@example.org','password':'Test-cosmic-239!'})
        return result
    def test_guest_claim_persistence_and_best_score(self):
        attempt = self.post('start', {'quiz': 'luce'}).json()['attempt']
        for i, a in enumerate([0,0,2]):
            result = self.post('answer', {'attempt': attempt, 'index': i, 'answer': a, 'score': 9999})
            self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['score'], 30)
        self.assertEqual(self.register().status_code, 200)
        self.assertEqual(Attempt.objects.get(pk=attempt).user.username, 'explorer')
        self.post('logout', {})
        self.assertEqual(self.client.get('/api/state/').json()['completed'], {})
        self.post('auth/login', {'email': 'explorer@example.org', 'password': 'Test-cosmic-239!'})
        self.assertEqual(self.client.get('/api/state/').json()['completed'], {'luce':30})
        second = self.post('start', {'quiz':'luce'}).json()['attempt']
        for i in range(3): self.post('answer', {'attempt':second, 'index':i, 'answer':1})
        self.assertEqual(self.client.get('/api/state/').json()['completed'], {'luce':30})
        self.assertTrue(User.objects.get(username='explorer').check_password('Test-cosmic-239!'))
        self.assertEqual(User.objects.get(username='explorer').email, 'explorer@example.org')
    def test_ownership_replay_and_validation(self):
        attempt = self.post('start', {'quiz':'luce'}).json()['attempt']
        self.assertEqual(self.post('answer', {'attempt':attempt, 'index':0, 'answer':0}, Client()).status_code, 404)
        self.assertEqual(self.post('answer', {'attempt':'bad', 'index':0, 'answer':0}).status_code, 404)
        self.assertEqual(self.post('answer', {'attempt':attempt, 'index':0, 'answer':True}).status_code, 400)
        self.assertEqual(self.post('answer', {'attempt':attempt, 'index':0, 'answer':0}).status_code, 200)
        self.assertEqual(self.post('answer', {'attempt':attempt, 'index':0, 'answer':0}).status_code, 409)
        self.assertEqual(Attempt.objects.get(pk=attempt).score, 10)
    def test_csrf_and_no_answer_keys(self):
        c=Client(enforce_csrf_checks=True)
        self.assertEqual(self.post('auth/register',{},c).status_code,403)
        q=self.client.get('/api/state/').json()['quizzes'][0]['questions'][0]
        self.assertEqual(len(q),2)
    def test_password_duplicate_and_login_throttle(self):
        self.assertEqual(self.post('auth/register', {'email':'test@example.org','username':'test','password':'123','password2':'123'}).status_code,400)
        self.assertEqual(self.register().status_code,200)
        self.assertEqual(self.register().status_code,200)
        for _ in range(11): response=self.post('auth/login', {'email':'nobody@example.org','password':'wrong'})
        self.assertEqual(response.status_code,429)

    def test_verification_reset_and_single_use(self):
        result = self.post('auth/register', {'email':'Demo@Example.org','username':'demo','password':'Cosmic-waves-321!','password2':'Cosmic-waves-321!'})
        self.assertEqual(result.status_code,200)
        user = User.objects.get(username='demo')
        self.assertFalse(user.is_active)
        self.assertEqual(self.post('auth/login',{'email':'demo@example.org','password':'Cosmic-waves-321!'}).status_code,401)
        token = parse_qs(urlsplit(mail.outbox[-1].body.splitlines()[-1]).query)['token'][0]
        # Merely opening the link (including mail scanners) must not activate.
        self.client.get('/account/verify/',{'token':token})
        user.refresh_from_db(); self.assertFalse(user.is_active)
        with patch('django.core.signing.time.time', return_value=__import__('time').time()+90000):
            self.assertContains(self.client.post('/account/verify/',{'token':token}), 'non è più valido')
        self.assertContains(self.client.post('/account/verify/',{'token':token}), 'Email confermata')
        self.assertContains(self.client.post('/account/verify/',{'token':token}), 'non è più valido')
        self.post('mail/reset',{'email':'demo@example.org'})
        values = {k:v[0] for k,v in parse_qs(urlsplit(mail.outbox[-1].body.splitlines()[-1]).query).items()}
        with self.settings(PASSWORD_RESET_TIMEOUT=-1):
            self.assertContains(self.client.get('/account/reset/',values), 'non è più valido')
        values.update(new_password1='Another-wave-678!',new_password2='Another-wave-678!')
        self.assertContains(self.client.post('/account/reset/', values), 'Password aggiornata')
        self.assertContains(self.client.post('/account/reset/', values), 'non è più valido')
        self.assertEqual(self.post('auth/login',{'email':'demo@example.org','password':'Cosmic-waves-321!'}).status_code,401)
        self.assertEqual(self.post('auth/login',{'email':'DEMO@example.org','password':'Another-wave-678!'}).status_code,200)

    @override_settings(DEBUG=False)
    def test_production_reset_does_not_expose_link(self):
        self.register()
        known=self.post('mail/reset',{'email':'explorer@example.org'}).json()
        unknown=self.post('mail/reset',{'email':'absent@example.org'}).json()
        self.assertEqual(known,unknown)
        self.assertNotIn('preview_url',known)
