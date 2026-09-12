#!/bin/sh
set -eu
python manage.py collectstatic --noinput
exec gunicorn --config gunicorn.conf.py config.wsgi:application
