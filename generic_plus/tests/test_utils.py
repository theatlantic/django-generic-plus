from pathlib import Path

from django import test
from django.test import override_settings

from generic_plus.utils import (
    get_generic_file_fields, get_media_path, get_relative_media_url)

from .test_filefield.models import TestGenericPlusModel, TwoFieldGenericPlusModel


MEDIA_ROOT = '/var/www/media'


@override_settings(MEDIA_ROOT=MEDIA_ROOT, MEDIA_URL='/media/')
class TestRelativeMediaUrl(test.SimpleTestCase):

    def test_media_url_is_stripped(self):
        self.assertEqual(get_relative_media_url('/media/test/foo.jpg'), 'test/foo.jpg')

    def test_media_root_is_stripped(self):
        self.assertEqual(
            get_relative_media_url('%s/test/foo.jpg' % MEDIA_ROOT), 'test/foo.jpg')

    def test_other_paths_are_left_alone(self):
        self.assertEqual(get_relative_media_url('test/foo.jpg'), 'test/foo.jpg')

    def test_media_path(self):
        self.assertEqual(
            get_media_path('/media/test/foo.jpg'), '%s/test/foo.jpg' % MEDIA_ROOT)


@override_settings(MEDIA_ROOT=Path(MEDIA_ROOT), MEDIA_URL='/media/')
class TestPathlibMediaRoot(test.SimpleTestCase):
    """MEDIA_ROOT is a pathlib.Path in Django's own startproject template."""

    def test_relative_media_url(self):
        self.assertEqual(
            get_relative_media_url('%s/test/foo.jpg' % MEDIA_ROOT), 'test/foo.jpg')

    def test_media_path(self):
        self.assertEqual(
            get_media_path('/media/test/foo.jpg'), '%s/test/foo.jpg' % MEDIA_ROOT)


class TestGenericFileFields(test.SimpleTestCase):

    def test_fields_are_returned_in_declaration_order(self):
        self.assertEqual(
            [f.name for f in get_generic_file_fields(TwoFieldGenericPlusModel)],
            ['file_one', 'file_two'])

    def test_model_with_one_field(self):
        self.assertEqual(
            [f.name for f in get_generic_file_fields(TestGenericPlusModel)],
            ['test_file'])
