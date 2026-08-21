from django import test
from django.apps import apps
from django.contrib.admin.options import ModelAdmin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory

from generic_plus import models
from generic_plus.admin import append_inlines_to_registered_admins
from generic_plus.apps import GenericPlusConfig
from generic_plus.fields import GenericForeignFileField
from generic_plus.models import patch_django, patch_model_admin
from generic_plus.patching import ORIGINAL_ATTR

from .test_filefield.models import (
    SecondTestGenericPlusModel, TestGenericPlusModel, TwoFieldGenericPlusModel)


OWN_FIELD = TestGenericPlusModel._meta.get_field('test_file')
FOREIGN_FIELD = SecondTestGenericPlusModel._meta.get_field('test_file')


class SlugOnlyModelAdmin(ModelAdmin):

    fields = ['slug']


class ForeignInlineModelAdmin(ModelAdmin):
    """Declares an inline for a GenericForeignFileField of another model."""

    inlines = [FOREIGN_FIELD.get_inline_admin_formset()]


def generic_plus_inlines(model_admin):
    return [i for i in model_admin.inlines
            if isinstance(getattr(i, 'field', None), GenericForeignFileField)]


def generic_plus_inline_instances(model_admin, request):
    return [i for i in model_admin.get_inline_instances(request)
            if isinstance(getattr(i, 'field', None), GenericForeignFileField)]


class TestAppConfig(test.SimpleTestCase):

    def test_app_config_is_used(self):
        self.assertIsInstance(apps.get_app_config('generic_plus'), GenericPlusConfig)

    def test_ready_installed_the_patches(self):
        self.assertTrue(models._patched)

    def test_patch_django_returns_early_once_patched(self):
        wrapper = ModelAdmin.__init__
        patch_django()
        self.assertIs(ModelAdmin.__init__, wrapper)

    def test_patching_a_second_time_stays_single_layered(self):
        original = getattr(ModelAdmin.__init__, ORIGINAL_ATTR)
        self.assertIsNone(getattr(original, ORIGINAL_ATTR, None))

        patch_model_admin()

        self.assertIsNot(ModelAdmin.__init__, original)
        self.assertIs(getattr(ModelAdmin.__init__, ORIGINAL_ATTR), original)
        model_admin = ModelAdmin(TestGenericPlusModel, AdminSite())
        self.assertEqual(len(generic_plus_inlines(model_admin)), 1)


class TestAdminIntegration(test.TestCase):

    def setUp(self):
        self.site = AdminSite()
        self.request = RequestFactory().get('/admin/')
        self.request.user = User(is_superuser=True, is_active=True)

    def test_inline_appended_to_plain_model_admin(self):
        model_admin = ModelAdmin(TestGenericPlusModel, self.site)
        inlines = generic_plus_inlines(model_admin)
        self.assertEqual(len(inlines), 1)
        self.assertEqual(inlines[0].field.name, 'test_file')

    def test_inline_not_appended_to_the_model_admin_class(self):
        ModelAdmin(TestGenericPlusModel, self.site)
        self.assertEqual(list(ModelAdmin.inlines), [])

    def test_inline_instance_present_when_field_in_fieldsets(self):
        model_admin = ModelAdmin(TestGenericPlusModel, self.site)
        self.assertEqual(len(generic_plus_inline_instances(model_admin, self.request)), 1)

    def test_inline_instance_dropped_when_field_not_in_fieldsets(self):
        model_admin = SlugOnlyModelAdmin(TestGenericPlusModel, self.site)
        self.assertEqual(len(generic_plus_inlines(model_admin)), 1)
        self.assertEqual(len(generic_plus_inline_instances(model_admin, self.request)), 0)

    def test_formfield_for_dbfield_passes_the_parent_admin(self):
        model_admin = ModelAdmin(TestGenericPlusModel, self.site)
        db_field = TestGenericPlusModel._meta.get_field('test_file')
        formfield = model_admin.formfield_for_dbfield(db_field, request=self.request)
        self.assertIs(formfield.parent_admin, model_admin)
        self.assertIs(formfield.widget.parent_admin, model_admin)
        self.assertIs(formfield.widget.request, self.request)

    def test_inlines_are_appended_in_field_declaration_order(self):
        model_admin = ModelAdmin(TwoFieldGenericPlusModel, self.site)
        self.assertEqual(
            [i.field.name for i in generic_plus_inlines(model_admin)],
            ['file_one', 'file_two'])

    def test_an_inline_for_another_models_field_is_left_alone(self):
        model_admin = ForeignInlineModelAdmin(TestGenericPlusModel, self.site)
        fields = [i.field for i in generic_plus_inlines(model_admin)]
        self.assertEqual(fields, [FOREIGN_FIELD, OWN_FIELD])

    def test_the_inline_is_not_appended_twice(self):
        class DeclaredInlineModelAdmin(ModelAdmin):
            inlines = [OWN_FIELD.get_inline_admin_formset()]

        model_admin = DeclaredInlineModelAdmin(TestGenericPlusModel, self.site)
        self.assertEqual([i.field for i in generic_plus_inlines(model_admin)], [OWN_FIELD])


class TestRegisteredAdminCatchUp(test.TestCase):
    """
    Admins registered before generic_plus's ready() ran (the usual case, since
    django.contrib.admin autodiscovers admin modules from its own ready())
    still get their inline.
    """

    def register_unpatched(self):
        site = AdminSite(name='catch-up')
        site.register(TestGenericPlusModel)
        model_admin = site._registry[TestGenericPlusModel]
        # Stands in for an admin instantiated before the patches were
        # installed, which is what the catch-up exists to fix up.
        model_admin.inlines = []
        return site, model_admin

    def test_inline_appended_after_the_fact(self):
        site, model_admin = self.register_unpatched()
        append_inlines_to_registered_admins()
        self.assertEqual(len(generic_plus_inlines(model_admin)), 1)

    def test_catch_up_is_idempotent(self):
        site, model_admin = self.register_unpatched()
        append_inlines_to_registered_admins()
        append_inlines_to_registered_admins()
        self.assertEqual(len(generic_plus_inlines(model_admin)), 1)
