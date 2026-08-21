import pytest
from django.conf import settings


if 'nested_admin' not in settings.INSTALLED_APPS:
    pytest.skip(
        "requires DJANGO_SETTINGS_MODULE=generic_plus.tests.settings_nested",
        allow_module_level=True)

pytest.importorskip("nested_admin")

from django.contrib.auth.models import User  # noqa: E402
from django.test import RequestFactory  # noqa: E402
from nested_admin.nested import NestedInlineModelAdminMixin  # noqa: E402

from generic_plus.fields import GenericForeignFileField  # noqa: E402
from generic_plus.patching import ORIGINAL_ATTR  # noqa: E402

from .nested_app.admin import NestedParentAdmin, site  # noqa: E402
from .test_filefield.models import TestNestedParent  # noqa: E402


def generic_plus_inlines(inlines):
    return [i for i in inlines
            if isinstance(getattr(i, 'field', None), GenericForeignFileField)]


@pytest.fixture
def admin_request():
    request = RequestFactory().get('/admin/')
    request.user = User(is_superuser=True, is_active=True)
    return request


@pytest.fixture
def child_inline(admin_request):
    """The NestedStackedInline for a model with a GenericForeignFileField."""
    model_admin = NestedParentAdmin(TestNestedParent, site)
    inline, = model_admin.get_inline_instances(admin_request)
    return inline


def test_nested_admin_copied_the_patched_method():
    assert hasattr(NestedInlineModelAdminMixin.get_inline_instances, ORIGINAL_ATTR)


def test_nested_inline_has_the_generic_plus_inline(child_inline):
    assert len(generic_plus_inlines(child_inline.inlines)) == 1


def test_nested_inline_drops_the_inline_when_field_not_in_fieldsets(
        child_inline, admin_request):
    inline_instances = child_inline.get_inline_instances(admin_request, None)
    assert generic_plus_inlines(inline_instances) == []
