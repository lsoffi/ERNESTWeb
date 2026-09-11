# ERNEST Community — Django

Working local prototype retaining the approved community design. It provides email/password registration with a public nickname, email verification, password reset, login/logout, guest quizzes and authenticated profiles. Scores are computed server-side; totals use each quiz's best completed attempt. Guest attempts are transferred to the account when signing in, as explained in the form. Nicknames are normalized to lowercase.

## Local preview

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
DJANGO_DEBUG=1 .venv/bin/python manage.py migrate
DJANGO_DEBUG=1 .venv/bin/python manage.py runserver 127.0.0.1:8771
```

Open http://127.0.0.1:8771/. Local SQLite is ignored by Git. Use test credentials only. Email is written to ignored preview-mails/ files; DEBUG responses also expose a local test link for convenience. No real messages are sent. The frontend preview in ../community-preview remains independent.

Tests: `DJANGO_DEBUG=1 .venv/bin/python manage.py test community`.

## CERN connection (pending DBoD)

Install requirements-mysql.txt instead of requirements.txt. Supply these through PaaS Secrets/environment, never source control:

- DJANGO_SECRET_KEY: unique random production secret
- DJANGO_DEBUG=0
- DJANGO_ALLOWED_HOSTS: exact public hostname
- DJANGO_CSRF_TRUSTED_ORIGINS: full HTTPS origin
- MYSQL_HOST, MYSQL_PORT, MYSQL_DATABASE, MYSQL_USER, MYSQL_PASSWORD
- MYSQL_SSL_CA: mounted CERN database CA file path
- PUBLIC_BASE_URL: exact HTTPS origin used for email links (never derived from request headers)
- EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, DEFAULT_FROM_EMAIL: authorized SMTP service
- TRUST_PROXY=1 only after verifying the ingress overwrites X-Forwarded-Proto

Production fails closed without a secret or MySQL configuration. Credentials, TLS certificate details and network connectivity must be verified against the provisioned DBoD instance. This connection is not yet tested. Apply migrations once in a deployment job, then collectstatic and run Gunicorn on port 8080. Do not migrate automatically in each web worker. No SQLite demo data should be copied to production.

The application uses Django password hashing, CSRF protection, private sessions, per-owner attempt access, transactional answer processing and database-backed request throttling. Test concurrency on MySQL before deployment. Rate limiting currently uses REMOTE_ADDR, so behind a proxy the IP bucket may be shared; set trustworthy client-IP handling at ingress before public launch.

Schedule `python manage.py cleanup_community` daily to remove anonymous attempts after 24 hours, expired sessions and old rate buckets. Authenticated completed attempts are retained; define retention and account deletion procedures before public use.

## Still required for public launch

- Connect and validate CERN MySQL, check backup/restore settings and deployment health checks.
- Replace local preview banner and review real quiz content.
- Configure and verify real email delivery (verification and reset), account deletion and privacy notice with the project.
- Run `manage.py check --deploy` with real configuration and test HTTPS, proxy configuration, concurrent submissions and login throttling.

Nothing in this directory has been deployed to CERN yet. The CERN ernest-test sample remains separate.

Email addresses are normalized to lowercase and stored uniquely. Unverified accounts cannot log in. Verification links expire after 24 hours and require a confirmation POST; reset links expire after one hour and become invalid after use. Public API profiles contain no email. Old nickname-only prototype accounts require an email migration before they can log in; no address is guessed or marked verified.
