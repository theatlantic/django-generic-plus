import re

import django
from django.core.exceptions import ObjectDoesNotExist
from django.forms.widgets import Input
from django.conf import settings
from django.contrib.admin import helpers
from django.contrib.admin.sites import site
from django.db.models.fields.files import FieldFile
from django.template.loader import render_to_string
from django.utils import six

from generic_plus.compat import compat_rel_to


class GenericForeignFileWidget(Input):

    template = "generic_plus/custom_field.html"

    def __init__(self, attrs=None, field=None):
        self.field = field
        self.attrs = attrs.copy() if attrs is not None else {}

    def get_context_data(self, name, value, attrs=None, bound_field=None):
        attrs = attrs or {}
        attrs.update({
            'type': self.input_type,
            'name': name,
        })
        final_attrs = self.build_attrs(attrs)

        formfield = getattr(bound_field, 'field', None)
        related = getattr(formfield, 'related', None)
        dbfield = getattr(related, 'field', None)
        file_field = getattr(dbfield, 'file_field', None)
        if django.VERSION > (1, 9):
            rel_model = getattr(getattr(dbfield, 'remote_field', None), 'model', None)
        else:
            rel_model = getattr(getattr(dbfield, 'rel', None), 'to', None)

        obj = None
        file_value = ''

        if not value:
            obj = None
        elif isinstance(value, FieldFile):
            obj = value.related_object
            file_value = value.name
            if file_value.startswith('/') and getattr(obj, self.field.name):
                file_value = getattr(obj, self.field.name).name
            value = getattr(obj, 'pk', None)
        elif rel_model and isinstance(value, six.string_types) and not value.isdigit():
            file_value = value
            if bound_field and getattr(bound_field, 'form', None):
                if not bound_field.form.prefix or name.startswith(bound_field.form.prefix):
                    formset_prefix = name
                else:
                    formset_prefix = bound_field.form.add_prefix(name)
                generic_field = getattr(bound_field.db_file_field, 'generic_field', None)
                if generic_field:
                    pk_name = compat_rel_to(generic_field)._meta.pk.name
                else:
                    pk_name = 'id'
                value = bound_field.form.data.get("%s-0-%s" % (
                    formset_prefix, pk_name))
        if rel_model and isinstance(value, six.integer_types) or (isinstance(value, six.string_types) and value.isdigit()):
            if not obj or not file_value:
                try:
                    obj = rel_model.objects.get(pk=value)
                except ObjectDoesNotExist:
                    pass
                else:
                    if getattr(obj, self.field.rel_file_field_name):
                        file_value = getattr(obj, self.field.rel_file_field_name).name
        else:
            obj = value
            try:
                value = obj.pk
            except AttributeError:
                obj = None
        if file_value and file_value.startswith(settings.MEDIA_ROOT):
            file_value = re.sub(r'^%s/?' % re.compile(settings.MEDIA_ROOT), '', file_value)

        if rel_model and isinstance(obj, rel_model) and not getattr(obj, self.field.rel_file_field_name) and file_value:
            setattr(obj, self.field.rel_file_field_name, file_value)

        if value and obj is None and rel_model:
            obj = rel_model.objects.get(pk=value)

        final_attrs['value'] = value or ''

        formset = self.get_inline_admin_formset(name, value, instance=obj, bound_field=bound_field)
        return {
            'instance': obj,
            'value': value,
            'upload_to': getattr(file_field, 'upload_to', ''),
            'file_value': file_value,
            'inline_admin_formset': formset,
            'prefix': name,
            'media_url': settings.MEDIA_URL,
            'final_attrs': final_attrs,
        }

    def render(self, name, value, attrs=None, bound_field=None):
        # If the name ends with "-id" then we are rendering the auto-appended
        # inline after a form submission with validation errors. If we were to
        # render this widget we would have duplicate inlines, so we check for
        # this condition and return.
        if name.endswith('-id'):
            return ""

        ctx = self.get_context_data(name, value, attrs, bound_field)
        return render_to_string(self.template, ctx)

    def get_inline_admin_formset(self, name, value, instance=None, bound_field=None, inline_cls=None):
        formfield = getattr(bound_field, 'field', None)
        related = getattr(formfield, 'related', None)
        dbfield = getattr(related, 'field', None)

        if dbfield is None:
            return None
        request = getattr(formfield, 'request', None)
        inline_cls = dbfield.get_inline_admin_formset()
        inline = inline_cls(dbfield.model, site)

        FormSet = inline.get_formset(request, obj=instance)

        formset_kwargs = {
            'data': getattr(request, 'POST', None) or bound_field.form.data or None,
            'prefix': name,
        }
        if instance:
            formset_kwargs['instance'] = bound_field.form.instance
            qs = instance.__class__._default_manager
            if self.field.field_identifier_field_name:
                field_identifier = getattr(instance, self.field.field_identifier_field_name)
                qs = qs.filter(field_identifier=field_identifier)
            formset_kwargs['queryset'] = qs

        formset = FormSet(**formset_kwargs)
        parent_admin = getattr(self, 'parent_admin', None)
        root_admin = getattr(parent_admin, 'root_admin', parent_admin)
        fieldsets = list(inline.get_fieldsets(request, instance))
        readonly = list(inline.get_readonly_fields(request, instance))
        return helpers.InlineAdminFormSet(inline, formset,
            fieldsets, readonly_fields=readonly, model_admin=root_admin)

    def value_from_datadict(self, data, files, name):
        """
        During form submission, field.widget.value_from_datadict() is used
        to get the value from the submitted POST data. The arguments `data`
        and `files` correspond to `request.POST` and `request.FILES`,
        respectively.

        This method differs from its parent method in that it checks _both_
        data and files for ``name`` (the parent checks only data). The value
        can be in files if the form was submitted using the fallback
        django.forms.FileField formfield.
        """
        return data.get(name, files.get(name, None))


def generic_fk_file_widget_factory(widget_cls=GenericForeignFileWidget, related=None, **attrs):
    return type('GenericForeignFileWidget', (widget_cls,), attrs)
    widget_attrs = {
        '__module__': widget_cls.__module__,
        'related': related,
        'parent_model': getattr(related, 'model', None),
        'rel_field': getattr(related, 'field', None),
    }
    widget_attrs.update(attrs)
    return type('GenericForeignFileWidget', (widget_cls,), widget_attrs)
