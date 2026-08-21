import types

from django.conf import settings
from django.contrib.admin.options import ModelAdmin
from django.contrib.admin.utils import flatten_fieldsets
from django.core import checks

from generic_plus.fields import GenericForeignFileField
from generic_plus.utils import get_generic_file_fields


__all__ = ('GenericPlusModelAdminMixin', 'autopatch_applies',
           'append_generic_file_inlines', 'filter_generic_file_inlines',
           'append_inlines_to_registered_admins', 'check_admins_have_inlines')


def autopatch_applies(model_admin):
    """
    Whether the inline appended by the monkeypatched ``__init__`` should be
    appended to ``model_admin``.
    """
    if isinstance(model_admin, GenericPlusModelAdminMixin):
        return False
    return getattr(settings, 'GENERIC_PLUS_AUTOPATCH_ADMIN', True)


def append_generic_file_inlines(model_admin, model):
    """
    Append the hidden inline to ``model_admin.inlines`` through which each
    GenericForeignFileField on ``model`` saves its related object.
    """
    generic_fk_fields = get_generic_file_fields(model)

    if not len(generic_fk_fields):
        return

    # ModelAdmin.inlines is defined as a mutable on that class, so we need to
    # copy it before we append (otherwise we'd modify the `inlines` attribute
    # for all ModelAdmins).
    try:
        model_admin.inlines = list(model_admin.inlines)
    except (AttributeError, TypeError):
        model_admin.inlines = []

    # Prevent duplicate inlines being added
    existing_inline_fields = {getattr(i, 'field', None) for i in model_admin.inlines}

    for field in generic_fk_fields:
        if field not in existing_inline_fields:
            model_admin.inlines.append(field.get_inline_admin_formset())


def filter_generic_file_inlines(model_admin, request, obj, inline_instances):
    """Skip generic-plus inlines if the field is not in fieldsets."""
    fieldsets = None

    def skip_inline_instance(inline):
        nonlocal fieldsets
        f = getattr(inline, 'field', None)
        if not isinstance(f, GenericForeignFileField):
            return False
        if fieldsets is None:
            # get_fieldsets() builds a form class, so it is left until an
            # inline that might be dropped actually turns up.
            fieldsets = flatten_fieldsets(model_admin.get_fieldsets(request, obj=obj))
        return f.name not in fieldsets

    if isinstance(inline_instances, types.GeneratorType):
        return (i for i in inline_instances if not(skip_inline_instance(i)))
    else:
        return [i for i in inline_instances if not(skip_inline_instance(i))]


def append_inlines_to_registered_admins():
    """Patch admins that were instantiated before the patches were installed."""
    from django.contrib.admin.sites import all_sites

    for site in all_sites:
        for model, model_admin in site._registry.items():
            if autopatch_applies(model_admin):
                append_generic_file_inlines(model_admin, model)


def check_admins_have_inlines(app_configs=None, **kwargs):
    """
    ``generic_plus.W001``: a registered admin cannot save one of its
    GenericForeignFileFields.

    Only reachable with ``GENERIC_PLUS_AUTOPATCH_ADMIN = False``, since the
    patched ``__init__`` appends the inline to every other admin. Without the
    inline, the admin renders the field's widget but discards whatever is
    submitted through it, with no error.
    """
    if getattr(settings, 'GENERIC_PLUS_AUTOPATCH_ADMIN', True):
        return []

    from django.contrib.admin.sites import all_sites

    app_labels = None if app_configs is None else {a.label for a in app_configs}
    messages = []

    for site in all_sites:
        for model, model_admin in site._registry.items():
            if app_labels is not None and model._meta.app_label not in app_labels:
                continue
            if isinstance(model_admin, GenericPlusModelAdminMixin):
                continue
            inline_fields = {getattr(i, 'field', None) for i in model_admin.inlines}
            missing = [f for f in get_generic_file_fields(model) if f not in inline_fields]
            for field in missing:
                messages.append(checks.Warning(
                    "%s has no inline for the GenericForeignFileField '%s', so "
                    "changes to that field are discarded on save." % (
                        type(model_admin).__name__, field.name),
                    hint=(
                        "GENERIC_PLUS_AUTOPATCH_ADMIN is False. Add "
                        "generic_plus.admin.GenericPlusModelAdminMixin to %s, or "
                        "append %s._meta.get_field('%s').get_inline_admin_formset() "
                        "to its inlines." % (
                            type(model_admin).__name__, model.__name__, field.name)),
                    obj=type(model_admin),
                    id='generic_plus.W001'))

    return messages


class GenericPlusModelAdminMixin(object):
    """
    Adds generic-plus support to a ModelAdmin explicitly.

    This mixin is only needed with ``GENERIC_PLUS_AUTOPATCH_ADMIN = False``.
    Under the default (True), the patch in ``generic_plus.models`` appends the
    same inline during ``__init__``.
    """

    def __init__(self, *args, **kwargs):
        if isinstance(self, ModelAdmin):
            model, admin_site = (tuple(args) + (None, None))[0:2]
            if not model:
                model = kwargs.get('model')
        else:
            model = self.model

        append_generic_file_inlines(self, model)

        super(GenericPlusModelAdminMixin, self).__init__(*args, **kwargs)

    def get_inline_instances(self, request, obj=None):
        # InlineModelAdmin has no get_inline_instances, and the mixin is
        # documented as applying to any admin class with a
        # GenericForeignFileField, inlines included.
        parent = super(GenericPlusModelAdminMixin, self)
        if not hasattr(parent, 'get_inline_instances'):
            return []
        inline_instances = parent.get_inline_instances(request, obj)
        return filter_generic_file_inlines(self, request, obj, inline_instances)

    def formfield_for_dbfield(self, db_field, **kwargs):
        if isinstance(db_field, GenericForeignFileField):
            return db_field.formfield(parent_admin=self, **kwargs)
        return super(GenericPlusModelAdminMixin, self).formfield_for_dbfield(db_field, **kwargs)
