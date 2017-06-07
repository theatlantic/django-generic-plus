import os
import re

from django.conf import settings


__all__ = ('get_media_path', 'get_relative_media_url')


re_url_slashes = re.compile(r'(?:\A|(?<=/))/')
re_path_slashes = re.compile(r'(?<=/)/')


def get_media_path(url):
    """Determine media URL's system file."""
    MEDIA_ROOT = os.path.abspath(settings.MEDIA_ROOT)
    re_media_url = re.compile(r'^%s' % re.escape(settings.MEDIA_URL))
    path = MEDIA_ROOT + '/' + re_media_url.sub('', url)
    return re_path_slashes.sub('', path)


def get_relative_media_url(path, clean_slashes=True):
    """Determine system file's media URL without MEDIA_URL prepended."""
    if path.startswith(settings.MEDIA_URL):
        url = path[len(settings.MEDIA_URL):]
    elif path.startswith(settings.MEDIA_ROOT):
        url = path[len(settings.MEDIA_ROOT):]
    else:
        url = path
    if clean_slashes:
        url = re_url_slashes.sub('', url)
    return url
