import json

from django import test
from django.conf import settings
from django.contrib.admin.options import ModelAdmin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory

from .test_filefield.models import TestFileModel, TwoFieldGenericPlusModel


LEGACY_CONTEXT_KEYS = {
    'instance', 'value', 'upload_to', 'file_value', 'inline_admin_formset',
    'prefix', 'media_url', 'final_attrs',
}


class TestWidgetContext(test.TestCase):

    def setUp(self):
        self.site = AdminSite()
        self.request = RequestFactory().get('/admin/')
        self.request.user = User(is_superuser=True, is_active=True)
        self.instance = TwoFieldGenericPlusModel.objects.create(
            slug="two-fields", file_one="test/foo.txt")
        self.related = TestFileModel.objects.create(
            content_object=self.instance, file="test/foo.txt", field_identifier="one")

    def get_bound_field(self, name='file_one', request=None):
        request = self.request if request is None else request
        model_admin = ModelAdmin(TwoFieldGenericPlusModel, self.site)
        form_cls = model_admin.get_form(request, obj=self.instance)
        form = form_cls(instance=self.instance)
        return form[name]

    def get_context(self, name='file_one', request=None):
        bound_field = self.get_bound_field(name, request)
        widget = bound_field.field.widget
        return widget.get_context_data(name, bound_field.value(), bound_field=bound_field)

    def test_render(self):
        bound_field = self.get_bound_field()
        html = bound_field.field.widget.render(
            'file_one', bound_field.value(), bound_field=bound_field)
        self.assertIn('name="file_one-0-id"', html)
        self.assertIn('data-prefix="file_one"', html)
        self.assertIn('id="file_one-group"', html)

    def test_legacy_context_keys_are_retained(self):
        ctx = self.get_context()
        self.assertEqual(LEGACY_CONTEXT_KEYS - set(ctx), set())
        self.assertEqual(ctx['prefix'], 'file_one')
        self.assertEqual(ctx['upload_to'], 'test')
        self.assertEqual(ctx['media_url'], settings.MEDIA_URL)
        self.assertEqual(ctx['file_value'], 'test/foo.txt')
        self.assertEqual(ctx['instance'], self.related)
        self.assertIsNotNone(ctx['inline_admin_formset'])
        self.assertEqual(ctx['final_attrs']['name'], 'file_one')

    def test_field_identifier(self):
        self.assertEqual(self.get_context('file_one')['field_identifier'], 'one')
        self.assertEqual(self.get_context('file_two')['field_identifier'], 'two')

    def test_formset_prefix(self):
        ctx = self.get_context()
        self.assertEqual(ctx['formset_prefix'], 'file_one')
        self.assertEqual(ctx['formset_prefix'], ctx['inline_admin_formset'].formset.prefix)

    def test_csrf_token(self):
        ctx = self.get_context()
        self.assertTrue(ctx['csrf_token'])
        self.assertEqual(ctx['csrf_token'], ctx['config']['csrfToken'])

    def test_csrf_token_is_none_without_a_request(self):
        db_field = TwoFieldGenericPlusModel._meta.get_field('file_one')
        formfield = db_field.formfield()
        self.assertIsNone(formfield.widget.request)
        ctx = formfield.widget.get_context_data('file_one', None)
        self.assertIsNone(ctx['csrf_token'])
        self.assertIsNone(ctx['config']['csrfToken'])

    def test_config(self):
        ctx = self.get_context()
        self.assertEqual(set(ctx['config']), {
            'uploadTo', 'mediaUrl', 'fieldIdentifier', 'csrfToken'})
        self.assertEqual(ctx['config']['uploadTo'], 'test')
        self.assertEqual(ctx['config']['mediaUrl'], settings.MEDIA_URL)
        self.assertEqual(ctx['config']['fieldIdentifier'], 'one')

    def test_config_json_round_trips(self):
        ctx = self.get_context()
        self.assertEqual(json.loads(ctx['config_json']), ctx['config'])

    def test_config_is_free_of_the_formset_prefix(self):
        ctx = self.get_context()
        self.assertNotIn('file_one', ctx['config_json'])
