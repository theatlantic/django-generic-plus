import django
from django import forms
from django.contrib.admin.widgets import AdminFileWidget
from django.core import validators
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.db import models
from django.db.models.fields.files import FieldFile
from django.forms.forms import BoundField
from django.forms.models import modelform_factory, ModelFormMetaclass
from django.utils import six
from django.utils.six.moves import range
from django.forms.formsets import TOTAL_FORM_COUNT
from django.utils.translation import ungettext

try:
    from django.utils.encoding import force_text
except ImportError:
    from django.utils.encoding import force_unicode as force_text

try:
    # Django 1.8+
    from django.contrib.contenttypes.forms import BaseGenericInlineFormSet
except ImportError:
    from django.contrib.contenttypes.generic import BaseGenericInlineFormSet

try:
    from django.forms.formsets import DEFAULT_MAX_NUM
except ImportError:
    DEFAULT_MAX_NUM = 1000

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
        if not db_field.missing_file_fallback:
            use_file_field = False
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
    max_num = 1
    can_order = False
    can_delete = True
    if django.VERSION > (1, 7):
        min_num = 1
        extra = 0
    else:
        min_num = 0
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

    def save(self, commit=True):
        """
        Saves model instances for every form, adding and changing instances
        as necessary, and returns the list of instances.
        """
        self.changed_objects = []
        self.deleted_objects = []
        self.new_objects = []

        # Copied lines are from BaseModelFormSet.save()
        if not commit:
            self.saved_forms = []
            def save_m2m():
                for form in self.saved_forms:
                    form.save_m2m()
            self.save_m2m = save_m2m
        # End copied lines from BaseModelFormSet.save()

        # The above if clause is the entirety of BaseModelFormSet.save(),
        # along with the following return:
        # return self.save_existing_objects(commit) + self.save_new_objects(commit)

        initial_form_count = self.initial_form_count()
        forms = []
        for i, form in enumerate(self.forms):
            form._is_initial = bool(i < initial_form_count)
            forms.append(form)

        form_instances = []
        saved_instances = []

        for form in forms:
            instance = self.get_saved_instance_for_form(form, commit, form_instances)
            if instance is not None:
                # Store saved instances so we can reference it for
                # sub-instanced nested beneath not-yet-saved instances.
                saved_instances += [instance]
            else:
                instance = form.instance
            if not self._should_delete_form(form):
                form_instances.append(instance)

        return saved_instances

    def get_saved_instance_for_form(self, form, commit, form_instances=None):
        pk_name = None
        if form.instance and form.instance._meta.pk:
            pk_name = form.instance._meta.pk.name
        pk_val = None
        if not form.errors and hasattr(form, 'cleaned_data'):
            pk_val = form.cleaned_data.get(pk_name)
        # Inherited models will show up as instances of the parent in
        # cleaned_data
        if isinstance(pk_val, models.Model):
            pk_val = pk_val.pk
        if pk_val is not None:
            try:
                setattr(form.instance, pk_name, pk_val)
            except ValueError:
                pk_attname = form.instance._meta.pk.get_attname()
                setattr(form.instance, pk_attname, pk_val)

        if form._is_initial:
            instances = self.save_existing_objects([form], commit)
        else:
            instances = self.save_new_objects([form], commit)
        if len(instances):
            return instances[0]
        else:
            return None

    def save_new(self, form, commit=True):
        """
        Identical to the parent method, except `get_for_model` is passed
        `for_concrete_model=self.for_concrete_model`.
        """
        from django.contrib.contenttypes.models import ContentType
        try:
            content_type = ContentType.objects.get_for_model(self.instance,
                for_concrete_model=self.for_concrete_model)
        except TypeError:
            # Django <= 1.5
            if not self.for_concrete_model:
                raise
            else:
                content_type = ContentType.objects.get_for_model(self.instance)
        setattr(form.instance, self.ct_field.get_attname(), content_type.pk)
        setattr(form.instance, self.ct_fk_field.get_attname(),
            self.instance.pk)
        return form.save(commit=commit)

    def save_existing(self, form, instance, commit=True):
        from django.contrib.contenttypes.models import ContentType
        try:
            content_type = ContentType.objects.get_for_model(self.instance,
                for_concrete_model=self.for_concrete_model)
        except TypeError:
            # Django <= 1.5
            if not self.for_concrete_model:
                raise
            else:
                content_type = ContentType.objects.get_for_model(self.instance)
        setattr(form.instance, self.ct_field.get_attname(), content_type.pk)
        setattr(form.instance, self.ct_fk_field.get_attname(), self.instance.pk)
        return form.save(commit=commit)

    def get_queryset(self):
        if not self.data:
            return super(BaseGenericFileInlineFormSet, self).get_queryset()

        if not hasattr(self, '__queryset'):
            pk_keys = ["%s-%s" % (self.add_prefix(i), self.model._meta.pk.name)
                       for i in range(0, self.initial_form_count())]
            pk_vals = [self.data.get(pk_key) for pk_key in pk_keys if self.data.get(pk_key)]

            mgr = self.model._default_manager
            if django.VERSION > (1, 6):
                # Django 1.6
                qs = mgr.get_queryset()
            else:
                # Django <= 1.5
                qs = mgr.get_query_set()

            qs = qs.filter(pk__in=pk_vals)

            # If the queryset isn't already ordered we need to add an
            # artificial ordering here to make sure that all formsets
            # constructed from this queryset have the same form order.
            if not qs.ordered:
                qs = qs.order_by(self.model._meta.pk.name)

            self.__queryset = qs
        return self.__queryset

    def save_existing_objects(self, initial_forms=None, commit=True):
        """
        Identical to parent class, except ``self.initial_forms`` is replaced
        with ``initial_forms``, passed as parameter.
        """
        from django.contrib.contenttypes.models import ContentType

        if not initial_forms:
            return []

        saved_instances = []

        forms_to_delete = self.deleted_forms

        for form in initial_forms:
            pk_name = self._pk_field.name

            if not hasattr(form, '_raw_value'):
                # Django 1.9+
                raw_pk_value = form.fields[pk_name].widget.value_from_datadict(
                    form.data, form.files, form.add_prefix(pk_name))
            else:
                raw_pk_value = form._raw_value(pk_name)

            # clean() for different types of PK fields can sometimes return
            # the model instance, and sometimes the PK. Handle either.
            if self._should_delete_form(form):
                pk_value = raw_pk_value
            else:
                try:
                    pk_value = form.fields[pk_name].clean(raw_pk_value)
                except ValidationError:
                    # The current form's instance was initially nested under
                    # a form that was deleted, which causes the pk clean to
                    # fail (because the instance has been deleted). To get
                    # around this we clear the pk and save it as if it were new.
                    form.data[form.add_prefix(pk_name)] = ''
                    saved_instances.extend(self.save_new_objects([form], commit))
                    continue
                pk_value = getattr(pk_value, 'pk', pk_value)

            obj = None
            if obj is None and form.instance and pk_value:
                model_cls = form.instance.__class__
                try:
                    obj = model_cls.objects.get(pk=pk_value)
                except model_cls.DoesNotExist:
                    if pk_value and force_text(form.instance.pk) == force_text(pk_value):
                        obj = form.instance
            if obj is None:
                obj = self._existing_object(pk_value)

            if form in forms_to_delete:
                self.deleted_objects.append(obj)
                if hasattr(self, 'delete_existing'):
                    self.delete_existing(obj, commit=commit)
                else:
                    if commit:
                        obj.delete()
                continue

            # fk_val: The value one should find in the form's foreign key field
            old_ct_val = ct_val = ContentType.objects.get_for_model(self.instance.__class__).pk
            old_fk_val = fk_val = self.instance.pk
            if form.instance.pk:
                original_instance = self.model.objects.get(pk=form.instance.pk)
                fk_field = getattr(self, 'fk', getattr(self, 'ct_fk_field', None))
                if fk_field:
                    old_fk_val = getattr(original_instance, fk_field.get_attname())
                ct_field = getattr(self, 'ct_field', None)
                if ct_field:
                    old_ct_val = getattr(original_instance, ct_field.get_attname())

            if form.has_changed() or fk_val != old_fk_val or ct_val != old_ct_val:
                self.changed_objects.append((obj, form.changed_data))
                saved_instances.append(self.save_existing(form, obj, commit=commit))
                if not commit:
                    self.saved_forms.append(form)
        return saved_instances

    def save_new_objects(self, extra_forms=None, commit=True):
        """
        Identical to parent class, except ``self.extra_forms`` is replaced
        with ``extra_forms``, passed as parameter, and self.new_objects is
        replaced with ``new_objects``.
        """
        new_objects = []

        if extra_forms is None:
            return new_objects

        for form in extra_forms:
            if not form.has_changed():
                continue
            # If someone has marked an add form for deletion, don't save the
            # object.
            if self.can_delete and self._should_delete_form(form):
                continue
            new_objects.append(self.save_new(form, commit=commit))
            if not commit:
                self.saved_forms.append(form)

        self.new_objects.extend(new_objects)
        return new_objects

    def full_clean(self):
        """
        Cleans all of self.data and populates self._errors and
        self._non_form_errors.
        """
        self._errors = []
        self._non_form_errors = self.error_class()

        if not self.is_bound:  # Stop further processing.
            return
        for i in range(0, self.total_form_count()):
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
    if django.VERSION < (1, 9):
        model = field.rel.to
    else:
        model = field.remote_field.model
    ct_field = model._meta.get_field(field.content_type_field_name)
    ct_fk_field = model._meta.get_field(field.object_id_field_name)
    exclude = [ct_field.name, ct_fk_field.name]

    fields = getattr(formset, 'fields', None)
    if not fields:
        fields = modelform_factory(model, exclude=exclude).base_fields

    def formfield_for_dbfield(db_field, **kwargs):
        kwargs.pop('request', None)
        if formfield_callback is not None:
            return formfield_callback(db_field, **kwargs)
        else:
            return db_field.formfield(**kwargs)

    def has_changed(self):
        return bool(self.changed_data)

    form_class_attrs = {
        'has_changed': has_changed,
        "model": model,
        field.rel_file_field_name: forms.CharField(required=False),
        "formfield_callback": formfield_for_dbfield,
        "Meta": type('Meta', (object,), {
            "fields": fields,
            "exclude": exclude,
            "model": model,
        }),
        '__module__': formset.__module__,
    }

    form_class_attrs.update(form_attrs or {})
    GenericForeignFileForm = ModelFormMetaclass('GenericForeignFileForm', (forms.ModelForm,), form_class_attrs)

    if GenericForeignFileForm.base_fields.get(field.field_identifier_field_name):
        field_id_formfield = GenericForeignFileForm.base_fields[field.field_identifier_field_name]
        field_id_formfield.widget = forms.HiddenInput()
        field_id_formfield.initial = getattr(field, field.field_identifier_field_name)

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
