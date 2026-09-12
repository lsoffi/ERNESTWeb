"""Local/CI tests only. Never use this settings module to serve the application."""
import os
if os.environ.get('MYSQL_HOST'):
    raise RuntimeError('Remove deployment database credentials before running tests')
from .settings import *
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
if os.environ.get('COMMUNITY_TEST_MYSQL') == '1':
    host = os.environ.get('TEST_MYSQL_HOST', '127.0.0.1')
    if host not in ('127.0.0.1', 'localhost'):
        raise RuntimeError('Tests must use an isolated loopback MySQL, never CERN DBOD')
    DATABASES = {'default': {
        'ENGINE': 'django.db.backends.mysql', 'HOST': host,
        'PORT': os.environ.get('TEST_MYSQL_PORT', '3306'),
        'NAME': 'ernest_test', 'USER': os.environ.get('TEST_MYSQL_USER', 'root'),
        'PASSWORD': os.environ.get('TEST_MYSQL_PASSWORD', ''),
        'OPTIONS': {'charset': 'utf8mb4', 'init_command': "SET sql_mode='STRICT_TRANS_TABLES'"},
        'TEST': {'NAME': 'test_ernest_security'},
    }}
