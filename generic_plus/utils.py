import os
import re

from django.conf import settings


__all__ = ('get_media_path', 'get_relative_media_url', 'get_generic_file_fields',
           'get_media_root', 'get_media_url')


re_url_slashes = re.compile(r'(?:\A|(?<=/))/')
re_path_slashes = re.compile(r'(?<=/)/')


def get_generic_file_fields(model):
    """Returns a list of GenericForeignFileFields on a given model"""
    from generic_plus.fields import GenericForeignFileField

    opts = model._meta
    m2m_fields = [f for f in opts.get_fields() if f.many_to_many and not f.auto_created]
    # dict.fromkeys() deduplicates while keeping declaration order, which is
    # the order the fields' inlines get appended to a ModelAdmin in.
    m2m_related_fields = dict.fromkeys(m2m_fields + list(opts.private_fields))
    return [f for f in m2m_related_fields if isinstance(f, GenericForeignFileField)]


def get_media_root():
    """``settings.MEDIA_ROOT`` as a string; it is often a ``pathlib.Path``."""
    return os.fspath(settings.MEDIA_ROOT)


def get_media_url():
    """``settings.MEDIA_URL`` as a string; it is often a lazy object."""
    return str(settings.MEDIA_URL)


def get_media_path(url):
    """Determine media URL's system file."""
    MEDIA_ROOT = os.path.abspath(get_media_root())
    re_media_url = re.compile(r'^%s' % re.escape(get_media_url()))
    path = MEDIA_ROOT + '/' + re_media_url.sub('', url)
    return re_path_slashes.sub('', path)


def get_relative_media_url(path, clean_slashes=True):
    """Determine system file's media URL without MEDIA_URL prepended."""
    media_url = get_media_url()
    media_root = get_media_root()
    if path.startswith(media_url):
        url = path[len(media_url):]
    elif path.startswith(media_root):
        url = path[len(media_root):]
    else:
        url = path
    if clean_slashes:
        url = re_url_slashes.sub('', url)
    return url
