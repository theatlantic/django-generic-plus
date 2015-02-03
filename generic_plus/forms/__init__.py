import six

from six.moves import xrange

from django import forms
from django.contrib.admin.widgets import AdminFileWidget
from django.contrib.contenttypes.generic import BaseGenericInlineFormSet
from django.core import validators
from django.core.files.uploadedfile import UploadedFile
from django.db import models
from django.db.models.fields.files import FieldFile
from django.forms.forms import BoundField
from django.forms.formsets import TOTAL_FORM_COUNT
from django.utils.translation import ungettext

try:
    from django.forms.formsets import DEFAULT_MAX_NUM
except ImportError:
    DEFAULT_MAX_NUM = 1000

from django.forms.models import ModelFormMetaclass
from django.core.exceptions import ValidationError

from .widgets import generic_fk_file_widget_factory, GenericForeignFileWidget


class GenericForeignFileBoundField(BoundField):

    db_file_field = None

    def __init__(self, form, field, name):
        super(GenericForeignFileBoundField, self).__init__(form, field, name)
        db_field = getattr(getattr(field, 'related', None), 'field', None)
        self.db_file_field = getattr(db_field, 'file_field', None)
        value = self.value()
        use_file_field = False
        if form.is_bound and isinstance(value, six.string_types) and not value.isdigit():
            formset_total_count_name = '%s-%s' % (form.add_prefix(name), forms.formsets.TOTAL_FORM_COUNT)
            if formset_total_count_name not in form.data:
                use_file_field = True
        # If the FieldFile has a filename, but no corresponding
        # generic related object (as it would, for instance, on instances
        # with files originally saved with a vanilla models.FileField)
        # then we use the standard FileField formfield.
        if isinstance(value, FieldFile) and value.name and not value.related_object:
            use_file_field = True
        # If this is a form submission from the FileField formfield (above),
        # then the value can be a django UploadedFile
        elif isinstance(value, UploadedFile):
            use_file_field = True
        # Swap out the GenericForeignFileFormField with a django.forms.FileField
        if use_file_field and self.db_file_field:
            widget = AdminFileWidget
            if form._meta.widgets and form._meta.widgets.get(name):
                widget = form._meta.widgets[name]
            self.field = self.db_file_field.formfield(**{
                'required': field.required,
                'label': field.label,
                'initial': field.initial,
                'widget': widget,
                'help_text': field.help_text,
            })

    def value(self):
        val = super(GenericForeignFileBoundField, self).value()
        if not self.db_file_field or not getattr(self.form, 'instance', None):
            return val
        if isinstance(self.field, forms.FileField) and isinstance(val, six.string_types):
            val = self.db_file_field.attr_class(self.form.instance, self.db_file_field, val)
        return val

    def as_widget(self, widget=None, attrs=None, only_initial=False):
        widget = widget or self.field.widget
        attrs = attrs or {}

        if self.auto_id and 'id' not in attrs and 'id' not in widget.attrs:
            attrs['id'] = self.html_initial_id if only_initial else self.auto_id

        name = self.html_initial_name if only_initial else self.html_name

        widget_kwargs = {'attrs': attrs}
        if isinstance(widget, GenericForeignFileWidget):
            widget_kwargs['bound_field'] = self

        return widget.render(name, self.value(), **widget_kwargs)


class GenericForeignFileFormField(forms.Field):

    def __init__(self, *args, **kwargs):
        widget_kwargs = kwargs.pop('widget_kwargs', None) or {}
        widget = kwargs.pop('widget', None)
        if isinstance(widget, type):
            if not issubclass(GenericForeignFileWidget):
                widget = GenericForeignFileWidget(field=self, **widget_kwargs)
        elif not isinstance(widget, GenericForeignFileWidget):
            widget = GenericForeignFileWidget(field=self, **widget_kwargs)
        kwargs['widget'] = widget
        super(GenericForeignFileFormField, self).__init__(*args, **kwargs)

    def to_python(self, value):
        value = super(GenericForeignFileFormField, self).to_python(value)
        if value in validators.EMPTY_VALUES:
            return None

        # value can be an UploadedFile if the form was submitted with the
        # fallback FileField formfield
        if isinstance(value, UploadedFile):
            return value

        if isinstance(value, six.string_types) and not value.isdigit():
            return value

        try:
            value = int(six.text_type(value))
        except (ValueError, TypeError):
            raise ValidationError(self.error_messages['invalid'])
        return value


def generic_fk_file_formfield_factory(widget=None, related=None, **attrs):
    widget = widget or generic_fk_file_widget_factory(related=related)
    formfield_attrs = {
        '__module__': GenericForeignFileFormField.__module__,
        'widget': widget,
        'related': related,
    }
    formfield_attrs.update(attrs)
    return type('GenericForeignFileFormField', (GenericForeignFileFormField,), formfield_attrs)


class BaseGenericFileInlineFormSet(BaseGenericInlineFormSet):

    extra_fields = None
    min_num = 0
    max_num = 1
    can_order = False
    can_delete = True
    extra = 1
    label = "Upload"
    prefix_override = None

    def __init__(self, *args, **kwargs):
        self.label = kwargs.pop('label', None) or self.label
        self.extra = kwargs.pop('extra', None) or self.extra
        self.extra_fields = kwargs.pop('extra_fields', None) or self.extra_fields
        if hasattr(self.extra_fields, 'iter'):
            for field in self.extra_fields:
                self.fields.append(field)

        if self.prefix_override:
            if kwargs.get('prefix') and self.prefix_override in kwargs['prefix']:
                pass
            else:
                kwargs['prefix'] = self.prefix_override

        super(BaseGenericFileInlineFormSet, self).__init__(*args, **kwargs)

    def initial_form_count(self):
        """
        In the event that the formset fields never rendered, don't raise a
        ValidationError, but return the sensible value (0)
        """
        try:
            return super(BaseGenericFileInlineFormSet, self).initial_form_count()
        except ValidationError:
            return 0

    def total_form_count(self):
        """See the docstring for initial_form_count()"""
        try:
            return super(BaseGenericFileInlineFormSet, self).total_form_count()
        except ValidationError:
            return 0

    @classmethod
    def get_default_prefix(cls):
        if cls.prefix_override:
            return cls.prefix_override
        else:
            return super(BaseGenericFileInlineFormSet, cls).get_default_prefix()

    def save_existing_objects(self, commit=True):
        """
        Identical to the parent method, except for the try/except ValidationError
        logic inside the self.initial_forms for loop.
        """
        self.changed_objects = []
        self.deleted_objects = []
        if not self.initial_forms:
            return []

        saved_instances = []

        for form in self.initial_forms:
            pk_name = self._pk_field.name
            raw_pk_value = form._raw_value(pk_name)

            # clean() for different types of PK fields can sometimes return
            # the model instance, and sometimes the PK. Handle either.
            try:
                pk_value = form.fields[pk_name].clean(raw_pk_value)
            except forms.ValidationError:
                # If a ValidationError was caused by a DoesNotExist error,
                # this means that the object was deleted in another formset's
                # save (e.g., if a generic foreign file field inline was attached
                # to another inline, in a nested fashion)
                try:
                    pk_value = self.model.objects.get(**{pk_name: raw_pk_value})
                except self.model.DoesNotExist:
                    continue
                else:
                    raise

            pk_value = getattr(pk_value, 'pk', pk_value)

            obj = self._existing_object(pk_value)
            if self.can_delete and self._should_delete_form(form):
                self.deleted_objects.append(obj)
                obj.delete()
                continue
            if form.has_changed():
                self.changed_objects.append((obj, form.changed_data))
                saved_instances.append(self.save_existing(form, obj, commit=commit))
                if not commit:
                    self.saved_forms.append(form)
        return saved_instances

    def full_clean(self):
        """
        Cleans all of self.data and populates self._errors and
        self._non_form_errors.
        """
        self._errors = []
        self._non_form_errors = self.error_class()

        if not self.is_bound: # Stop further processing.
            return
        for i in xrange(0, self.total_form_count()):
            form = self.forms[i]
            self._errors.append(form.errors)
        try:
            if (self.validate_max and
                self.total_form_count() - len(self.deleted_forms) > self.max_num) or \
                self.management_form.cleaned_data[TOTAL_FORM_COUNT] > self.absolute_max:
                raise ValidationError(ungettext(
                    "Please submit %d or fewer forms.",
                    "Please submit %d or fewer forms.", self.max_num) % self.max_num,
                    code='too_many_forms',
                )
            # Give self.clean() a chance to do cross-form validation.
            self.clean()
        except ValidationError as e:

            if getattr(e, 'code', None) != 'missing_management_form':
                if e.messages != [u'ManagementForm data is missing or has been tampered with']:
                    self._non_form_errors = self.error_class(e.messages)


def generic_fk_file_formset_factory(field=None, formset=BaseGenericFileInlineFormSet,
        form_attrs=None, formset_attrs=None, formfield_callback=None, prefix=None,
        for_concrete_model=True):
    model = field.rel.to
    ct_field = model._meta.get_field(field.content_type_field_name)
    ct_fk_field = model._meta.get_field(field.object_id_field_name)
    exclude = [ct_field.name, ct_fk_field.name]

    def formfield_for_dbfield(db_field, **kwargs):
        if isinstance(db_field, models.FileField) and db_field.model == model:
            kwargs['widget'] = forms.TextInput
        kwargs.pop('request', None)
        if formfield_callback is not None:
            return formfield_callback(db_field, **kwargs)
        else:
            return db_field.formfield(**kwargs)

    def has_changed(self):
        if not self.changed_data and not any(self.cleaned_data.values()):
            return False
        return True

    form_class_attrs = {
        'has_changed': has_changed,
        "model": model,
        field.rel_file_field_name: forms.CharField(required=False),
        "formfield_callback": formfield_for_dbfield,
        "Meta": type('Meta', (object,), {
            "fields": formset.fields,
            "exclude": exclude,
            "model": model,
        }),
        '__module__': formset.__module__,
    }

    form_class_attrs.update(form_attrs or {})
    GenericForeignFileForm = ModelFormMetaclass('GenericForeignFileForm', (forms.ModelForm,), form_class_attrs)

    inline_formset_attrs = {
        "formfield_callback": formfield_for_dbfield,
        "ct_field": ct_field,
        "ct_fk_field": ct_fk_field,
        "exclude": exclude,
        "form": GenericForeignFileForm,
        "model": model,
        '__module__': formset.__module__,
        'prefix_override': prefix,
        'default_prefix': prefix,
        'max_num': DEFAULT_MAX_NUM,
        'absolute_max': max(DEFAULT_MAX_NUM, (formset_attrs or {}).get('max_num') or 0),
        'for_concrete_model': for_concrete_model,
        'validate_max': False,
    }
    if field.field_identifier_field_name:
        field_identifier = getattr(field, field.field_identifier_field_name)
        inline_formset_attrs[field.field_identifier_field_name] = field_identifier
    inline_formset_attrs.update(formset_attrs or {})

    return type('GenericForeignFileInlineFormSet', (formset,), inline_formset_attrs)
