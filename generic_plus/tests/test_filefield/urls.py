from django.conf.urls import include, url
from django.contrib import admin

# Explicitly import to register the admins for the test models
import generic_plus.tests.test_filefield.admin  # noqa


urlpatterns = [url(r'^admin/', include(admin.site.urls))]

try:
    import grappelli  # noqa
except ImportError:
    pass
else:
    urlpatterns += [url(r"^grappelli/", include("grappelli.urls"))]
