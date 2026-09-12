#!/bin/sh
set -eu
# Run from community-app in an isolated environment, without CERN credentials.
[ -z "${MYSQL_HOST:-}" ] || { echo "Remove deployment database credentials before running checks" >&2; exit 1; }
export DJANGO_DEBUG=1
export ACCOUNTS_ENABLED=1
python -m pip check
python -m pip_audit -r requirements.txt --no-deps --disable-pip --strict
python manage.py makemigrations --check --dry-run
python manage.py collectstatic --noinput
python manage.py test community --settings=config.test_settings --noinput
COMMUNITY_TEST_MYSQL=1 python manage.py test community --settings=config.test_settings --noinput
