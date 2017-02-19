import django
from django.conf.urls import include, url
from django.contrib import admin

# Explicitly import to register the admins for the test models
import generic_plus.tests.test_curation.admin  # noqa


if django.VERSION > (1, 9):
    urlpatterns = [url(r'^admin/', admin.site.urls)]
else:
    urlpatterns = [url(r'^admin/', include(admin.site.urls))]
