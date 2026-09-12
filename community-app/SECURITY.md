# Security and release operations

This document describes controls in this revision, not a certification that a running deployment is secure. No application can be guaranteed immune to compromise. Do not publish credentials, recovery material, database dumps or personal data in issues, logs or this repository.

## Controls in the application

- Production requires MySQL and certificate/hostname verification (`VERIFY_IDENTITY`); SQLite is only for local development. The database must use a dedicated application identity, never the DBOD administrator.
- Django password validation, password hashing, CSRF checks, secure production cookies and HTTPS remain enabled. Tokens expire; verification requires an explicit POST. Password reset invalidates existing password-based sessions.
- Registration enforces unique email and nickname. A duplicate does not overwrite an account or send a new registration email. Valid requests receive the same generic response whether the account already exists or is created. This avoids an explicit account-existence disclosure; synchronous email delivery can still introduce timing differences. An email delivery failure is logged as a fixed event and users can request a new confirmation.
- Attempts are scoped to the current account or guest session. MySQL row locking prevents concurrent answers from awarding points twice. The leaderboard requires login and returns aggregates plus the current user's position.
- Rate budgets are stored centrally in MySQL with row locking, so multiple application workers share them. Keys are HMAC digests rather than raw addresses/emails. Budgets apply per address and, where relevant, per email or account. Request bodies are capped at 8 KiB. These limits reduce abuse; they are not network-level denial-of-service protection.
- Administrative access requires a confirmed TOTP authenticator in addition to a password and staff permissions. A normal community login does not grant administrative access. TOTP replay protection and throttling come from django-otp; administrative sessions expire after 30 minutes. Administrators cannot read passwords or edit their own privileges through this panel.
- Application logs omit raw URLs, query strings, IPs, headers, form values and exception details. Gunicorn records only route categories, response status and duration. Email failures retain a fixed event identifier. This deliberately limits production diagnostics; reproduce failures with synthetic data in an isolated environment instead of enabling public DEBUG.

## CERN deployment boundary

Follow the official [PaaS documentation](https://paas.docs.cern.ch/) and [DBOD guide](https://cern.ch/dbod-user-guide). The application continues to use supported S2I containers, Secrets and the external DBOD service; it does not require root privileges, host mounts, privileged containers or a public database Route.

PaaS documentation distinguishes platform/container logs from ingress logs and describes platform backups separately from external databases. Sanitizing application output does not alter CERN ingress or audit logs. Verify token-bearing URL handling with the service's logging facilities and restrict log access. DBOD backup coverage and a restore rehearsal must be checked separately; do not infer database backup coverage from PaaS backups.

CERN routers provide `X-Forwarded-For` for edge/re-encrypt routes: see [original client IP addresses](https://paas.docs.cern.ch/5._Exposing_The_Application/5-ip-addresses/). Configure `TRUSTED_PROXY_CIDRS` only after verifying the actual proxy peer addresses and network path. Never use all-address ranges or trust a browser-supplied header. Without this setting, forwarded addresses are ignored and visitors behind the same proxy share a conservative rate budget. This may throttle legitimate users, so validate the configuration before release. `TRUST_PROXY=1` separately requires a proxy that overwrites client-supplied forwarding-protocol headers.

Application operators remain responsible for their code, dependencies, permissions and deployment checks. This revision does not certify privacy arrangements, infrastructure policies, database backup settings or effective database privileges.

## Enroll administrators before enabling this revision

The first deployment requires the django-otp migrations and enrollment of each existing, verified staff account. Do not switch live traffic to the new image before this is complete.

1. Build the reviewed image without automatically replacing the serving deployment. Use an authenticated operator terminal with narrowly authorized access to the target environment; never put credential values in command arguments, manifests in Git, or job logs.
2. Record the current image digest and database backup/restore checkpoint. Run `python manage.py migrate --plan`, then apply the reviewed additive migrations with the migration identity. Do not give the serving application global database privileges for this operation.
3. From a private interactive terminal run `python manage.py enroll_admin_mfa NICKNAME --provisioning-file /ABSOLUTE/PRIVATE/DIRECTORY/otp.txt`. Use a directory accessible only to the operator, outside all served and repository directories. The command creates the file exclusively with mode 0600. Import its provisioning URI into the administrator's authenticator using an approved private transfer method, then enter the authenticator code in the terminal. Never display the URI in container logs, chat or screenshots. The file is removed on completion or failure; failed confirmation rolls back enrollment.
4. Run `python manage.py check --deploy` and `python manage.py security_preflight --database` using the serving configuration. The latter checks TLS, direct global grants and administrator enrollment without printing credentials or grants. Review schema-level privileges and inherited roles separately: this check is deliberately not a complete privilege audit. Verify the running application's identity has only required permissions on its schema, and network access is restricted to intended clients.
5. Verify password-only admin access is refused, then test password plus TOTP with the real administrator in the controlled environment. Confirm ordinary user login, verification/reset, quiz ownership, private leaderboard and language switching still work.
6. Publish through the normal CERN workflow, monitor sanitized errors and verify the public HTTPS route. Record commit and image digest. Do not use a development server in production.

If an authenticator is lost, an authorized operator must verify the administrator's identity through the team's established recovery channel. Run `python manage.py revoke_admin_mfa NICKNAME` in a private operator terminal, then enroll again. Revocation invalidates the device used by administrative sessions; it does not enable password-only administration. There is no public recovery endpoint or shared bypass code. Keep at least two separately enrolled, authorized operators for continuity.

## Dependency updates and automated checks

`requirements.in` defines supported runtime ranges. `requirements.txt` locks all runtime packages and hashes. `requirements-tools.in` and its generated lock file define verification tooling. Regenerate locks using Python 3.12 in an isolated environment, review the diff and rerun tests:

```sh
python -m pip install --require-hashes -r requirements-tools.txt
python -m piptools compile --upgrade --generate-hashes --strip-extras --no-emit-index-url --no-emit-trusted-host requirements.in
python -m piptools compile --upgrade --allow-unsafe --generate-hashes --strip-extras --no-emit-index-url --no-emit-trusted-host requirements-tools.in
python -m pip install --require-hashes -r requirements.txt
```

MySQL client development libraries and pkg-config are required to build mysqlclient. Rebuild the S2I image to incorporate base-image updates as well as Python updates; a source commit alone does not update deployed containers. MySQL server updates follow DBOD procedures and require compatibility checks.

The GitHub workflow runs dependency auditing, schema/static checks and tests against SQLite and a disposable MySQL 8.4 instance. It has read-only repository permissions and needs no CERN Secrets. Dependabot proposes weekly changes; no automatic merge or deployment is configured by these files.

**Activation prerequisite:** GitHub scheduled workflows and Dependabot configuration must be present on the repository's default branch. The daily workflow checks out the community publication branch. Keeping these files only on that publication branch does not activate daily checks or Dependabot. Push/PR checks also require publishing the commit and enabling Actions. Verify a successful run and configure maintainers' failure notifications before relying on automation.

Locally, use a disposable loopback-only MySQL instance and run `sh scripts/check_release.sh` with `TEST_MYSQL_PORT` as needed. Remove deployment database credentials first: the test settings reject `MYSQL_HOST`, restrict the test host to loopback, and use locmem email. Never run concurrency/load tests against CERN DBOD or real accounts. Python 3.12 is the deployment/CI target; a local run under another version does not replace that CI run.

On a vulnerability alert, assess exposure and update promptly; do not wait for a weekly update batch for an urgent fix. An audit with no findings only means no known findings in the consulted database at that time.

## Rollback, housekeeping and incidents

Keep the previous reviewed image digest and a verified DBOD recovery point before a release. For this additive MFA schema change, a code rollback can leave the new tables in place; do not reverse/drop tables or restore a whole database merely to roll back an image. The old image lacks the new MFA controls, so restrict administrative access if it must be restored. Rehearse restores on a separate database and account for writes made after a backup.

Schedule the existing `cleanup_community` command through the supported job facilities to remove expired guest attempts, rate buckets and sessions. Its presence in source does not mean a job has been scheduled. Define retention and account deletion separately.

For a suspected incident, restrict affected access, preserve relevant evidence through authorized CERN facilities, rotate compromised credentials in Secrets, invalidate affected sessions and follow the institutional incident process. Do not post data or secrets in public issues. Credentials that have been shared outside their intended secure channel should be rotated; code changes cannot undo their disclosure.

## Verification record

The September 2026 hardening work uses synthetic local test data only. Release acceptance requires the automated checks above plus the live-environment checks; no penetration-test certification or production database audit is implied by a passing test suite. Production MFA enrollment, trusted-proxy configuration, effective grants, backup restoration and activation of repository automation must be recorded by the operators before claiming those controls are operational.

Local verification on 2026-09-12: 31 tests passed against an isolated MySQL 8.4.11 instance; SQLite passed 29 tests with the two MySQL-only concurrency tests skipped. The local interpreter was Python 3.14. Gunicorn configuration, Django migration consistency, static collection and JavaScript syntax checks passed. Runtime dependency auditing reported no known vulnerabilities. The Python 3.12 GitHub workflow and CERN release checks still require execution after publishing/activation.
