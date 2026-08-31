from django.contrib import admin
from nested_admin import NestedModelAdmin, NestedStackedInline

from generic_plus.tests.test_filefield.models import TestNestedChild, TestNestedParent


class NestedChildInline(NestedStackedInline):
    """A nested inline whose fieldsets omit its model's generic file field."""

    model = TestNestedChild
    fields = ['slug']
    extra = 0


class NestedParentAdmin(NestedModelAdmin):

    inlines = [NestedChildInline]


site = admin.AdminSite(name='nested')
site.register(TestNestedParent, NestedParentAdmin)
