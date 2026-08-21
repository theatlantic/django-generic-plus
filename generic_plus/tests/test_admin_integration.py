from django import test
from django.apps import apps
from django.contrib.admin.options import ModelAdmin, StackedInline
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory, override_settings

from generic_plus import models
from generic_plus.admin import (
    GenericPlusModelAdminMixin, append_inlines_to_registered_admins,
    check_admins_have_inlines)
from generic_plus.apps import GenericPlusConfig
from generic_plus.fields import GenericForeignFileField
from generic_plus.models import patch_django, patch_model_admin
from generic_plus.patching import ORIGINAL_ATTR

from .test_filefield.models import (
    SecondTestGenericPlusModel, TestGenericPlusModel, TestNestedChild,
    TestNestedParent, TwoFieldGenericPlusModel)


OWN_FIELD = TestGenericPlusModel._meta.get_field('test_file')
FOREIGN_FIELD = SecondTestGenericPlusModel._meta.get_field('test_file')


class SlugOnlyModelAdmin(ModelAdmin):

    fields = ['slug']


class ForeignInlineModelAdmin(ModelAdmin):
    """Declares an inline for a GenericForeignFileField of another model."""

    inlines = [FOREIGN_FIELD.get_inline_admin_formset()]


class MixinModelAdmin(GenericPlusModelAdminMixin, ModelAdmin):

    pass


class MixinSlugOnlyModelAdmin(GenericPlusModelAdminMixin, ModelAdmin):

    fields = ['slug']


class MixinInline(GenericPlusModelAdminMixin, StackedInline):

    model = TestNestedChild
    fields = ['slug']


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


class TestAdminMixinOnAnInline(test.TestCase):
    """The mixin also applies to inline admins, which have no inlines of their own."""

    def setUp(self):
        self.site = AdminSite()
        self.request = RequestFactory().get('/admin/')
        self.request.user = User(is_superuser=True, is_active=True)

    def test_inline_appended(self):
        inline = MixinInline(TestNestedParent, self.site)
        self.assertEqual(
            [i.field.name for i in generic_plus_inlines(inline)], ['test_file'])

    def test_get_inline_instances_does_not_raise(self):
        inline = MixinInline(TestNestedParent, self.site)
        self.assertEqual(inline.get_inline_instances(self.request), [])


@override_settings(GENERIC_PLUS_AUTOPATCH_ADMIN=False)
class TestAdminAutopatchDisabled(test.TestCase):

    def setUp(self):
        self.site = AdminSite()
        self.request = RequestFactory().get('/admin/')
        self.request.user = User(is_superuser=True, is_active=True)

    def test_plain_model_admin_gets_no_inline(self):
        model_admin = ModelAdmin(TestGenericPlusModel, self.site)
        self.assertEqual(generic_plus_inlines(model_admin), [])

    def test_plain_model_admin_still_gets_the_parent_admin(self):
        """The widget needs it to render whatever inline it does have."""
        model_admin = ModelAdmin(TestGenericPlusModel, self.site)
        db_field = TestGenericPlusModel._meta.get_field('test_file')
        formfield = model_admin.formfield_for_dbfield(db_field, request=self.request)
        self.assertIs(formfield.widget.parent_admin, model_admin)

    def test_a_declared_inline_is_still_filtered_out(self):
        """
        Filtering is not gated on the setting: an admin that appends the inline
        itself needs it dropped from admins that omit the field just the same.
        """
        class DeclaredSlugOnlyModelAdmin(ModelAdmin):
            fields = ['slug']
            inlines = [OWN_FIELD.get_inline_admin_formset()]

        model_admin = DeclaredSlugOnlyModelAdmin(TestGenericPlusModel, self.site)
        self.assertEqual(len(generic_plus_inlines(model_admin)), 1)
        self.assertEqual(len(generic_plus_inline_instances(model_admin, self.request)), 0)

    def test_mixin_appends_the_inline(self):
        model_admin = MixinModelAdmin(TestGenericPlusModel, self.site)
        inlines = generic_plus_inlines(model_admin)
        self.assertEqual(len(inlines), 1)
        self.assertEqual(inlines[0].field.name, 'test_file')

    def test_mixin_keeps_the_inline_instance_when_field_in_fieldsets(self):
        model_admin = MixinModelAdmin(TestGenericPlusModel, self.site)
        self.assertEqual(len(generic_plus_inline_instances(model_admin, self.request)), 1)

    def test_mixin_drops_the_inline_instance_when_field_not_in_fieldsets(self):
        model_admin = MixinSlugOnlyModelAdmin(TestGenericPlusModel, self.site)
        self.assertEqual(len(generic_plus_inlines(model_admin)), 1)
        self.assertEqual(len(generic_plus_inline_instances(model_admin, self.request)), 0)

    def test_mixin_passes_the_parent_admin(self):
        model_admin = MixinModelAdmin(TestGenericPlusModel, self.site)
        db_field = TestGenericPlusModel._meta.get_field('test_file')
        formfield = model_admin.formfield_for_dbfield(db_field, request=self.request)
        self.assertIs(formfield.widget.parent_admin, model_admin)


class TestSystemCheck(test.SimpleTestCase):
    """generic_plus.W001, raised for admins that cannot save their file field."""

    def messages_for(self, model_admin_cls):
        return [m for m in check_admins_have_inlines() if m.obj is model_admin_cls]

    def register(self, model_admin_cls):
        # Held onto for the duration of the test: all_sites is a WeakSet.
        self.site = AdminSite(name='checks')
        self.site.register(TestGenericPlusModel, model_admin_cls)
        return model_admin_cls

    def test_no_warnings_while_autopatching(self):
        self.register(SlugOnlyModelAdmin)
        self.assertEqual(check_admins_have_inlines(), [])

    @override_settings(GENERIC_PLUS_AUTOPATCH_ADMIN=False)
    def test_warns_for_an_admin_without_the_inline(self):
        # Registered under a class of its own so that the admin sites other
        # tests leave behind in all_sites cannot contribute messages.
        class UnpatchedModelAdmin(ModelAdmin):
            fields = ['slug']

        self.register(UnpatchedModelAdmin)
        messages = self.messages_for(UnpatchedModelAdmin)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].id, 'generic_plus.W001')
        self.assertIn('test_file', messages[0].msg)

    @override_settings(GENERIC_PLUS_AUTOPATCH_ADMIN=False)
    def test_does_not_warn_for_a_mixin_admin(self):
        self.register(MixinModelAdmin)
        self.assertEqual(self.messages_for(MixinModelAdmin), [])

    @override_settings(GENERIC_PLUS_AUTOPATCH_ADMIN=False)
    def test_does_not_warn_for_an_admin_that_declares_the_inline(self):
        class DeclaredInlineModelAdmin(ModelAdmin):
            inlines = [OWN_FIELD.get_inline_admin_formset()]

        self.register(DeclaredInlineModelAdmin)
        self.assertEqual(self.messages_for(DeclaredInlineModelAdmin), [])

    @override_settings(GENERIC_PLUS_AUTOPATCH_ADMIN=False)
    def test_only_checks_the_apps_it_is_given(self):
        self.register(SlugOnlyModelAdmin)
        app_configs = [apps.get_app_config('contenttypes')]
        self.assertEqual(check_admins_have_inlines(app_configs=app_configs), [])


class TestRegisteredAdminCatchUp(test.TestCase):
    """
    Admins registered before generic_plus's ready() ran (the usual case, since
    django.contrib.admin autodiscovers admin modules from its own ready())
    still get their inline.
    """

    def register_unpatched(self):
        site = AdminSite(name='catch-up')
        with override_settings(GENERIC_PLUS_AUTOPATCH_ADMIN=False):
            site.register(TestGenericPlusModel)
        model_admin = site._registry[TestGenericPlusModel]
        self.assertEqual(generic_plus_inlines(model_admin), [])
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


class TestAdminMixinWithAutopatchEnabled(test.TestCase):
    """The mixin and the patches must not both apply."""

    def setUp(self):
        self.site = AdminSite()
        self.request = RequestFactory().get('/admin/')
        self.request.user = User(is_superuser=True, is_active=True)

    def test_inline_added_exactly_once(self):
        model_admin = MixinModelAdmin(TestGenericPlusModel, self.site)
        self.assertEqual(len(generic_plus_inlines(model_admin)), 1)
        self.assertEqual(len(generic_plus_inline_instances(model_admin, self.request)), 1)
