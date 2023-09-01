from django.urls import re_path
from django.contrib import admin

# Explicitly import to register the admins for the test models
import generic_plus.tests.test_curation.admin  # noqa


urlpatterns = [re_path(r'^admin/', admin.site.urls)]
