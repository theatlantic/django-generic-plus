import django
from django.conf.urls import include, url
from django.contrib import admin

# Explicitly import to register the admins for the test models
import generic_plus.tests.test_curation.admin  # noqa


urlpatterns = [url(r'^admin/', admin.site.urls)]
