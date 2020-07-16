#!/usr/bin/env python
import os
import tempfile

import django


try:
    import dj_database_url
except ImportError:
    dj_database_url = None


current_dir = os.path.abspath(os.path.dirname(__file__))
temp_dir = tempfile.mkdtemp()


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:'
    }
}

if dj_database_url is not None:
    DATABASES['default'] = dj_database_url.parse(
        os.environ.get('DATABASE_URL', 'sqlite://:memory:'))

SECRET_KEY = 'z-i*xqqn)r0i7leak^#clq6y5j8&tfslp^a4duaywj2$**s*0_'

if django.VERSION > (2, 0):
    MIGRATION_MODULES = {
        'auth': None,
        'contenttypes': None,
        'sessions': None,
    }

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [os.path.join(current_dir, 'test_filefield', 'templates')],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.contrib.auth.context_processors.auth',
            'django.template.context_processors.debug',
            'django.template.context_processors.i18n',
            'django.template.context_processors.media',
            'django.template.context_processors.static',
            'django.template.context_processors.tz',
            'django.template.context_processors.request',
            'django.contrib.messages.context_processors.messages',
        ],
    },
}]

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    'django.contrib.admin',
    'generic_plus',
)

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'generic_plus': {
            'handlers': ['console'],
            'level': 'WARNING',
        },
    },
}

SITE_ID = 1
MEDIA_ROOT = os.path.join(temp_dir, 'media')
MEDIA_URL = '/media/'
STATIC_URL = '/static/'
DEBUG_PROPAGATE_EXCEPTIONS = True
TEST_RUNNER = 'django.test.runner.DiscoverRunner'
