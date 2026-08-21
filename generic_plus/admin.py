import types

from django.contrib.admin.utils import flatten_fieldsets

from generic_plus.fields import GenericForeignFileField
from generic_plus.utils import get_generic_file_fields


__all__ = ('append_generic_file_inlines', 'filter_generic_file_inlines',
           'append_inlines_to_registered_admins')


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
            append_generic_file_inlines(model_admin, model)
