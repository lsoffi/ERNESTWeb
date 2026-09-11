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

class AdminTests(TestCase):
    def setUp(self):
        from .models import AccountEmail
        self.member = User.objects.create_user('member', email='member@example.org', password='test-only-Strong-738!')
        AccountEmail.objects.create(user=self.member, address=self.member.email, verified=True)
        self.manager = User.objects.create_superuser('manager', password='test-only-Strong-482!')

    def test_access_and_private_fields(self):
        self.assertEqual(self.client.get('/admin/auth/user/').status_code, 302)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get('/admin/auth/user/').status_code, 302)
        self.client.force_login(self.manager)
        response = self.client.get(f'/admin/auth/user/{self.member.pk}/change/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.member.password)
        self.assertNotContains(response, 'name="is_superuser"')
        self.assertNotContains(response, 'name="password"')

    def test_totals_and_disable(self):
        from .admin import MemberAdmin, community_admin
        from django.test import RequestFactory
        for quiz, score, finished in [('luce',10,True),('luce',30,True),('particelle',20,True),('indizi',10,False)]:
            Attempt.objects.create(user=self.member,session_key='test',quiz=quiz,score=score,finished=finished)
        admin = MemberAdmin(User, community_admin)
        obj = admin.get_queryset(RequestFactory().get('/')).get(pk=self.member.pk)
        self.assertEqual(admin.completed_quizzes(obj),2)
        self.assertEqual(admin.total_score(obj),50)
        self.client.force_login(self.manager)
        result = self.client.post(f'/admin/auth/user/{obj.pk}/change/', {'_save':'Salva'})
        self.assertEqual(result.status_code,302)
        obj.refresh_from_db()
        self.assertFalse(obj.is_active)

    def test_admin_csrf_and_throttle(self):
        strict=Client(enforce_csrf_checks=True)
        self.assertEqual(strict.post('/admin/login/',{'username':'manager','password':'wrong'}).status_code,403)
        for _ in range(11):
            result=self.client.post('/admin/login/',{'username':'manager','password':'wrong'})
        self.assertEqual(result.status_code,429)

@override_settings(SECURE_SSL_REDIRECT=True, SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True)
class AccountHTTPSFormTests(TestCase):
    def test_verify_with_csrf_and_same_origin_referrer(self):
        from django.core import signing
        from .models import AccountEmail
        user=User.objects.create_user('pending',email='pending@example.org',is_active=False)
        AccountEmail.objects.create(user=user,address=user.email)
        token=signing.dumps({'user':user.pk,'email':user.email},salt='ernest-verify')
        client=Client(enforce_csrf_checks=True)
        page=client.get('/account/verify/', {'token':token},secure=True)
        self.assertEqual(page['Referrer-Policy'],'same-origin')
        self.assertContains(page,'content="same-origin"')
        self.assertContains(page,'action="/account/verify/?lang=it"')
        csrf=client.cookies['csrftoken'].value
        self.assertEqual(client.post('/account/verify/',{'token':token},secure=True,HTTP_REFERER='https://testserver/account/verify/').status_code,403)
        result=client.post('/account/verify/',{'token':token,'csrfmiddlewaretoken':csrf},secure=True,HTTP_REFERER='https://testserver/account/verify/')
        self.assertContains(result,'Email confermata')
        user.refresh_from_db();self.assertTrue(user.is_active)

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class LanguageTests(TestCase):
    def test_language_selection_and_account_pages(self):
        for language, text in [('it','Il tuo account'),('fr','Votre compte'),('en','Your account')]:
            response=self.client.get('/account/verify/', {'lang':language})
            self.assertContains(response, f'<html lang="{language}">')
            self.assertContains(response, text)
            self.assertEqual(response.cookies['django_language'].value, language)
            self.assertContains(self.client.get('/'),f'<html lang="{language}">')

    def test_email_uses_selected_language(self):
        from django.utils import translation
        from .accounts import deliver
        from .i18n import CATALOGS
        user=User.objects.create_user('languageuser',email='language@example.org')
        for language in ['fr','en']:
            with translation.override(language):
                for purpose, subject in [('verify','Conferma la tua email — ERNEST'),('reset','Reimposta la password — ERNEST')]:
                    url=deliver(user,purpose)
                    self.assertEqual(mail.outbox[-1].subject,CATALOGS[language][subject])
                    self.assertEqual(parse_qs(urlsplit(url).query)['lang'],[language])

    def test_quiz_translation_coverage(self):
        from .views import QUIZZES
        from .i18n import CATALOGS
        for language,catalog in CATALOGS.items():
            for quiz in QUIZZES:
                texts=[quiz['title'],quiz['desc'],quiz['topic']]
                for question in quiz['questions']:
                    texts.extend([question[0],*question[1],question[3]])
                for text in texts:
                    self.assertIn(text,catalog,(language,text))

class LeaderboardTests(TestCase):
    def test_distribution_is_aggregate_and_rank_is_private(self):
        from .models import AccountEmail
        for nickname, scores, active, verified in [('alice',[10,30],True,True),('bob',[30],True,True),('carol',[10],True,True),('hidden',[30],False,True),('pending',[30],True,False)]:
            user=User.objects.create_user(nickname,email=nickname+'@example.org',is_active=active)
            AccountEmail.objects.create(user=user,address=user.email,verified=verified)
            for score in scores: Attempt.objects.create(user=user,session_key='test',quiz='luce',score=score,finished=True)
            Attempt.objects.create(user=user,session_key='test',quiz='particelle',score=30,finished=False)
        Attempt.objects.create(session_key='guest',quiz='luce',score=30,finished=True)
        self.assertEqual(self.client.get('/api/leaderboard/').status_code,401)
        self.client.force_login(User.objects.get(username='alice'))
        response=self.client.get('/api/leaderboard/')
        data=response.json()
        self.assertEqual(data['participants'],3)
        self.assertEqual(data['mine'],{'score':30,'rank':1})
        self.assertEqual(data['bands'][1]['count'],1)
        self.assertEqual(data['bands'][3]['count'],2)
        self.assertNotIn('alice',response.content.decode())
        self.assertNotIn('@example.org',response.content.decode())
        for nickname,rank in [('alice',1),('bob',1),('carol',3)]:
            self.client.force_login(User.objects.get(username=nickname))
            response=self.client.get('/api/leaderboard/')
            self.assertEqual(response.json()['mine']['rank'],rank)
            self.assertEqual(response['Cache-Control'],'private, no-store')
