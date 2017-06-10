"""
Defines GenericForeignFileField, a subclass of GenericRelation from
django.contrib.contenttypes.
"""
import itertools
import operator

import django
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import File
from django.core.files.uploadedfile import UploadedFile
from django.db import connection, router, models
from django.db.models.deletion import DO_NOTHING
from django.db.models.fields.files import FieldFile, FileDescriptor
from django.db.models.fields.related import RelatedField, Field, ManyToOneRel
from django.utils.functional import curry
from django.utils import six
from django.utils.six.moves import reduce

try:
    # Django 1.8+
    from django.contrib.contenttypes.fields import GenericRelation
except ImportError:
    from django.contrib.contenttypes.generic import GenericRelation

try:
    # Django 1.8+
    from django.contrib.contenttypes.admin import GenericInlineModelAdmin
except ImportError:
    from django.contrib.contenttypes.generic import GenericInlineModelAdmin

try:
    # Django 1.7+
    from django.contrib.contenttypes.fields import GenericRel
except ImportError:
    from django.contrib.contenttypes.generic import GenericRel

try:
    from django.db.models.fields.related import ForeignObject, ForeignObjectRel
except ImportError:
    # Django <= 1.5
    class ForeignObject(RelatedField, Field):
        pass

    class ForeignObjectRel(ManyToOneRel):
        def __init__(self, field, to, **kwargs):
            self.related_query_name = kwargs.pop('related_query_name', None)
            self.field = field
            super(ForeignObjectRel, self).__init__(to, self.field.name, **kwargs)

from generic_plus.compat import compat_rel, compat_rel_to
from generic_plus.forms import (
    generic_fk_file_formfield_factory, generic_fk_file_widget_factory)


class GenericForeignFileField(GenericRelation):
    """
    The base class for GenericForeignFileField; adds descriptors to the model.

    This field accepts the same keyword arguments as models.FileField. It
    enables GenericForeignFileField to act as both a FileField and a
    GenericForeignKey.

    If assigned to a model with name ``field_name``, allows retrieval of
    the generic related object's information by several attributes (via
    descriptors):

    getattr(instance, field_name):
            An instance of FieldFile, with obj.field_name.related_object
            as the generic related instance (or None if there is no
            related object). A getattr on ``field_name`` will perform a
            database query.
    getattr(instance, '%%s_raw' %% field_name):
            An instance of FieldFile that does not sync with the generic
            related object. Use this if you need to retrieve the file path
            but do not want to make a database query.
    getattr(instance, '%%s_generic_rel' %% field_name):
            The generic related manager for the field.
    """

    file_kwargs = None
    file_field = None

    generic_descriptor = None
    file_descriptor = None

    file_descriptor_cls = FileDescriptor
    file_field_cls = models.FileField
    rel_file_field_name = 'file'
    field_identifier_field_name = None

    def __init__(self, to, rel_file_field_name=None, field_identifier="",
            missing_file_fallback=True, **kwargs):
        """
        Parameters
        ----------
        to : Model or str
        rel_file_field_name : str
            Name of the FileField on the generic related model (e.g. "image",
            "file" [the default])
        field_identifier : str
            A string to uniquely identify the field on the model, allowing
            multiple GenericForeignFileFields to point to a single model class
        missing_file_fallback : bool
            If set to True (the default), the GenericForeignFileField widget
            will show the admin's file field widget in the event that there is
            a value on the model for the file field, but no corresponding row
            in the table with the generic foreign key.
        """
        self.rel_file_field_name = rel_file_field_name or self.rel_file_field_name
        self.field_identifier = field_identifier
        self.missing_file_fallback = missing_file_fallback

        self.file_kwargs = {
            'editable': (django.VERSION > (1, 10)),
            'default': '',
            'blank': True,
            'upload_to': kwargs.pop('upload_to', None),
            'storage': kwargs.pop('storage', None),
            'max_length': kwargs.pop('max_length', 100),
            'db_index': kwargs.pop('db_index', False),
            # width_field and height_field will be removed from this dict
            # if, in contribute_to_related_class(), the related FileField
            # is not found to be an instance of models.ImageField.
            'width_field': kwargs.pop('width_field', None),
            'height_field': kwargs.pop('height_field', None),
        }

        symmetrical = kwargs.pop('symmetrical', True)

        if issubclass(GenericRel, ForeignObjectRel):
            # Django 1.6
            kwargs['rel'] = GenericRel(self, to,
                related_name=kwargs.pop('related_name', None),
                limit_choices_to=kwargs.pop('limit_choices_to', None))
            kwargs['rel'].on_delete = DO_NOTHING
        else:
            # Django <= 1.5
            kwargs['rel'] = GenericRel(to,
                                related_name=kwargs.pop('related_name', None),
                                limit_choices_to=kwargs.pop('limit_choices_to', None),
                                symmetrical=symmetrical)
            kwargs['rel'].field = self

        # Override content-type/object-id field names on the related class
        self.object_id_field_name = kwargs.pop("object_id_field", "object_id")
        self.content_type_field_name = kwargs.pop("content_type_field", "content_type")
        self.field_identifier_field_name = kwargs.pop("field_identifier_field", self.field_identifier_field_name)

        self.for_concrete_model = kwargs.pop("for_concrete_model", True)

        kwargs.update({
            'blank': True,
            'editable': True,
            'serialize': False,
            'max_length': self.file_kwargs['max_length'],
        })

        if django.VERSION > (1, 9):
            kwargs['on_delete'] = models.CASCADE

        if isinstance(self, ForeignObject):
            # Django 1.6
            super(GenericRelation, self).__init__(
                to,
                from_fields=[self.object_id_field_name], to_fields=[], **kwargs)
        else:
            # Django <= 1.5
            models.Field.__init__(self, **kwargs)

        self.file_kwargs['db_column'] = kwargs.get('db_column', self.name)

    if (1, 6) < django.VERSION < (1, 8):
        # Prior to Django 1.6, Model._meta.get_field_by_name() never returned
        # virtual fields. django-generic-plus takes advantage of this fact in
        # order to have _both_ a virtual field (the generic relation) and a
        # local field (the FileField). In Django 1.6, get_field_by_name() will
        # return the virtual field if the field has the 'related' attr. To get
        # around this new inconvenience, we make an @property for related that
        # raises an AttributeError while Model._meta.init_name_map() is being
        # executed.
        def do_related_class(self, other, cls):
            from django.db.models.related import RelatedObject

            self.set_attributes_from_rel()
            self._related = RelatedObject(other, cls, self)
            if not cls._meta.abstract:
                self.contribute_to_related_class(other, self._related)

        @property
        def related(self):
            if hasattr(self.model._meta, '_name_map') or not hasattr(self.model._meta, '_related_objects_cache'):
                return self._related
            elif django.VERSION[0:2] == (1, 7):
                if hasattr(self.model._meta, '_related_objects_cache') and self._related not in self.model._meta._related_objects_cache:
                    return self._related
            raise AttributeError("'%s' object has no attribute 'related'" % type(self).__name__)

    def contribute_to_class(self, cls, name):
        self.generic_rel_name = '%s_generic_rel' % name
        self.raw_file_field_name = '%s_raw' % name
        self.file_field_name = name

        if hasattr(self, 'set_attributes_from_name'):
            self.set_attributes_from_name(name)
            self.file_kwargs['db_column'] = self.db_column or self.attname

        # Save a reference to which model this class is on for future use
        self.model = cls

        if django.VERSION > (1, 7):
            super(GenericRelation, self).contribute_to_class(cls, name, **{
                ('private_only' if django.VERSION > (1, 10) else 'virtual_only'): True,
            })
        else:
            super(GenericForeignFileField, self).contribute_to_class(cls, name)

        if django.VERSION >= (1, 8):
            self.column = self.file_kwargs['db_column']

        if not isinstance(self.file_field_cls, models.ImageField):
            self.file_kwargs.pop('width_field', None)
            self.file_kwargs.pop('height_field', None)
        else:
            if not self.file_kwargs['width_field']:
                del self.file_kwargs['width_field']
            if not self.file_kwargs['height_field']:
                del self.file_kwargs['height_field']

        self.__dict__['file_field'] = self.file_field_cls(**self.file_kwargs)
        ### HACK: manually fix creation counter
        self.file_field.creation_counter = self.creation_counter

        # This calls contribute_to_class() for the FileField
        parents = cls._meta.parents.keys()
        parent_field_names = []
        if parents:
            parent_fields = reduce(operator.add, [p._meta.local_fields for p in parents], [])
            parent_field_names = [f.name for f in parent_fields]
        # Don't duplicate the field when inherited from a parent model
        if self.file_field_name not in parent_field_names:
            # Don't add field to proxy models
            if not cls._meta.proxy:
                cls.add_to_class(self.file_field_name, self.file_field)

        # Add the descriptor for the generic relation
        generic_descriptor = GenericForeignFileDescriptor(self, self.file_field,
            for_concrete_model=self.for_concrete_model)
        # We use self.__dict__ to avoid triggering __get__()
        self.__dict__['generic_descriptor'] = generic_descriptor
        setattr(cls, self.generic_rel_name, generic_descriptor)

        # Add the descriptor for the FileField
        file_descriptor = GenericForeignFileDescriptor(self, self.file_field,
            is_file_field=True, for_concrete_model=self.for_concrete_model)
        self.__dict__['file_descriptor'] = file_descriptor
        setattr(cls, self.file_field_name, file_descriptor)

        self.file_field.__dict__.update({
            'generic_descriptor': generic_descriptor,
            'file_descriptor': file_descriptor,
            'db_field': self,
            'generic_field': getattr(cls, self.generic_rel_name),
        })
        setattr(cls, self.raw_file_field_name, self.file_descriptor_cls(self.file_field))

    def is_cached(self, instance):
        return hasattr(instance, self.get_cache_name())

    def get_prefetch_queryset(self, instances, queryset=None):
        models = set([type(i) for i in instances])

        # Handle case where instances are different models (and consequently,
        # different content types)
        if len(models) > 1:
            bulk_qsets = []
            for model, group in itertools.groupby(instances, type):
                model_instances = list(group)
                field = getattr(model, self.name)
                bulk_qsets.append(field.bulk_related_objects(model_instances))
            bulk_qset = reduce(operator.or_, bulk_qsets)

            def rel_obj_attr(rel_obj):
                content_type = getattr(rel_obj, "%s_id" % self.content_type_field_name)
                object_id = getattr(rel_obj, self.object_id_field_name)
                return (content_type, object_id)

            def get_ctype_obj_id(obj):
                field = getattr(obj.__class__, self.name)
                try:
                    content_type = ContentType.objects.get_for_model(obj, field.for_concrete_model)
                except TypeError:
                    # Django <= 1.5
                    if not field.for_concrete_model:
                        raise
                    else:
                        content_type = ContentType.objects.get_for_model(obj)
                return (content_type.pk, obj._get_pk_val())

            return (bulk_qset,
                rel_obj_attr,
                get_ctype_obj_id,
                True,
                self.attname)

        return (self.bulk_related_objects(instances),
            operator.attrgetter(self.object_id_field_name),
            lambda obj: obj._get_pk_val(),
            True,
            self.attname)

    if django.VERSION < (1, 7):
        get_prefetch_query_set = get_prefetch_queryset

    def bulk_related_objects(self, *args, **kwargs):
        """
        Return all objects related to ``objs`` via this ``GenericRelation``.

        """
        qs = super(GenericForeignFileField, self).bulk_related_objects(*args, **kwargs)
        if self.field_identifier_field_name:
            qs = qs.filter(**{"%s__exact" % self.field_identifier_field_name: self.field_identifier})
        return qs

    def south_init(self):
        """
        This method is called by south before it introspects the field.

        South assumes that this is a related field if self.rel is set and it
        is not None. While this is a reasonable assumption, and it is *mostly*
        true for GenericForeignFileField, it is incorrect as far as South is
        concerned; we need South to treat this as a FileField so that
        it creates a column in the containing model.

        To deal with this situation we conditionally return the same values as
        FileField from get_internal_type() and db_type() while south is
        introspecting the field, and otherwise return the values that would be
        returned by a GenericRelation (which are the same as those returned
        by a ManyToManyField)

        self.south_executing is the basis for the conditional logic. It is set
        to True in this method (south_init()) and then back to False in
        GenericForeignFileField.post_create_sql().
        """
        self.south_executing = True
        self._rel = self.rel
        self.rel = None

    def post_create_sql(self, style, db_table):
        """
        This method is called after south is done introspecting the field.

        See GenericForeignFileField.south_init() for more documentation
        about the reason this is overridden here.
        """
        self.south_executing = False
        if django.VERSION < (1, 8):
            if self.rel is None and hasattr(self, '_rel'):
                self.rel = self._rel
        return []

    def get_internal_type(self):
        """
        Related to the implementation of db_type(), returns the pre-existing
        Django Field class whose database column is the same as the current
        field class, if such a class exists.

        See GenericForeignFileField.south_init() for more documentation
        about the reason this is overridden here.
        """
        if getattr(self, 'south_executing', None):
            return 'FileField'
        else:
            # super() returns 'ManyToManyField'
            return super(GenericForeignFileField, self).get_internal_type()

    def db_type(self, connection):
        """
        Returns the database column data type for this field, for the provided
        connection.

        See GenericForeignFileField.south_init() for more documentation
        about the reason this is overridden here.
        """
        if getattr(self, 'south_executing', None):
            return models.Field.db_type(self, connection)
        else:
            # super() returns None
            return super(GenericForeignFileField, self).db_type(connection)

    def save_form_data(self, instance, data):
        super(GenericForeignFileField, self).save_form_data(instance, data)

        # pre_save returns getattr(instance, self.name), which is itself
        # the return value of the descriptor's __get__() method.
        # This method (GenericForeignFileDescriptor.__get__()) has side effects,
        # for the same reason that the descriptors of FileField and
        # GenericForeignKey have side-effects.
        #
        # So, although we don't _appear_ to be doing anything with the
        # value if not(isinstance(data, UploadedFile)), it is still
        # necessary to call pre_save() for the FileField part of the
        # instance's GenericForeignFileField to sync.
        value = self.pre_save(instance, False)

        # If we have a file uploaded via the fallback FileField, make
        # sure that it's saved.
        if isinstance(data, UploadedFile):
            if value and isinstance(value, FieldFile) and not value._committed:
                # save=True saves the instance. Since this field (GenericForeignFileField)
                # is considered a "related field" by Django, its save_form_data()
                # gets called after the instance has already been saved. We need
                # to resave it if we have a new file.
                value.save(value.name, value, save=True)
        else:
            instance.save()

    def formfield(self, **kwargs):
        factory_kwargs = {}
        if django.VERSION > (1, 9):
            factory_kwargs['related'] = getattr(self, 'remote_field', None)
        elif django.VERSION > (1, 8):
            factory_kwargs['related'] = getattr(self, 'rel', None)
        else:
            factory_kwargs['related'] = getattr(self, 'related', None)
        widget = kwargs.pop('widget', None) or generic_fk_file_widget_factory(**factory_kwargs)
        formfield = kwargs.pop('form_class', None) or generic_fk_file_formfield_factory(widget=widget, **factory_kwargs)
        widget.parent_admin = formfield.parent_admin = kwargs.pop('parent_admin', None)
        widget.request = formfield.request = kwargs.pop('request', None)
        formfield.file_field_name = widget.file_field_name = self.file_field_name

        if isinstance(widget, type):
            widget = widget(field=self)
        else:
            widget.field = self
        kwargs.update({
            'widget': widget,
            'form_class': formfield,
        })
        return super(GenericForeignFileField, self).formfield(**kwargs)

    def get_inline_admin_formset(self, formset_cls=None, form_attrs=None, **kwargs):
        from generic_plus.forms import generic_fk_file_formset_factory, BaseGenericFileInlineFormSet

        formset_cls = formset_cls or BaseGenericFileInlineFormSet

        attrs = {
            'model': compat_rel_to(self),
            'default_prefix': self.name,
            'field': self,
            'formset_kwargs': kwargs.pop('formset_kwargs', None) or {},
        }

        attrs.update(kwargs.pop('attrs', None) or {})

        if getattr(formset_cls, 'fields', None):
            attrs['fieldsets'] = ((None, {
                'fields': formset_cls.fields,
            }),)

        class GenericForeignFileInline(GenericInlineModelAdmin):

            # This InlineModelAdmin exists for dual purposes: to be displayed
            # inside of the GenericForeignFileField's widget, and as the mechanism
            # by which changes are saved when a ModelAdmin is saved. For the
            # latter purpose we would not want the inline to actually render,
            # as it would be a duplicate of the inline rendered in the
            # GenericForeignFileField. For this reason we set the template to an
            # empty html file.
            template = "generic_plus/blank.html"

            extra = 1
            max_num = 1

            if not attrs.get('get_formset'):
                def get_formset(self, request, obj=None, **kwargs):
                    formset = generic_fk_file_formset_factory(
                        formset=formset_cls,
                        formset_attrs=kwargs,
                        field=self.field,
                        prefix=self.default_prefix,
                        formfield_callback=curry(self.formfield_for_dbfield, request=request),
                        form_attrs=form_attrs)
                    if getattr(self, 'default_prefix', None):
                        formset.default_prefix = self.default_prefix
                    return formset
            else:
                get_formset = attrs.pop('get_formset')

        return type('GenericForeignFileInline', (GenericForeignFileInline,), attrs)

    @property
    def get_path_info(self):
        raise AttributeError("'%s' object has no attribute 'get_path_info'" % type(self).__name__)

    @property
    def get_lookup_constraint(self):
        raise AttributeError("'%s' object has no attribute 'get_lookup_constraint'" % type(self).__name__)

    def get_attname_column(self):
        attname = self.get_attname()
        column = self.db_column or attname
        return attname, column


class GenericForeignFileDescriptor(object):

    def __init__(self, field, file_field, is_file_field=False, for_concrete_model=True):
        self.field = field
        self.file_field = file_field
        self.is_file_field = is_file_field
        self.for_concrete_model = for_concrete_model

    def __get__(self, instance, instance_type=None):
        if instance is None:
            return self.field

        cache_name = self.field.get_cache_name()
        file_val = None

        if self.is_file_field:
            file_val = instance.__dict__[self.file_field.name]

        # Dynamically create a class that subclasses the related model's
        # default manager.
        rel_model = compat_rel_to(self.field)
        superclass = rel_model._default_manager.__class__
        RelatedManager = create_generic_related_manager(superclass)

        qn = connection.ops.quote_name

        manager_kwargs = {
            'prefetch_cache_name': self.field.attname,
        }

        if hasattr(compat_rel(self.field), 'symmetrical'):
            # Django <= 1.5
            manager_kwargs['symmetrical'] = (compat_rel(self.field).symmetrical and instance.__class__ == rel_model)

        if hasattr(self.field, 'get_joining_columns'):
            join_cols = self.field.get_joining_columns(reverse_join=True)[0]
        else:
            join_cols = [self.field.m2m_column_name(), self.field.m2m_reverse_name()]

        ct_manager = ContentType.objects.db_manager(instance._state.db)
        try:
            content_type = ct_manager.get_for_model(instance, for_concrete_model=self.for_concrete_model)
        except TypeError:
            # Django <= 1.5
            if not self.for_concrete_model:
                raise
            else:
                content_type = ct_manager.get_for_model(instance)

        manager = RelatedManager(
            model=rel_model,
            instance=instance,
            field=self.field,
            source_col_name=qn(join_cols[0]),
            target_col_name=qn(join_cols[1]),
            content_type=content_type,
            content_type_field_name=self.field.content_type_field_name,
            object_id_field_name=self.field.object_id_field_name,
            field_identifier_field_name=self.field.field_identifier_field_name,
            **manager_kwargs)

        if not manager.pk_val:
            val = None
        else:
            if not self.is_file_field:
                return manager

            try:
                val = getattr(instance, cache_name)
            except AttributeError:
                db = manager._db or router.db_for_read(rel_model, instance=instance)
                if django.VERSION > (1, 6):
                    qset = superclass.get_queryset(manager).using(db)
                else:
                    qset = superclass.get_query_set(manager).using(db)

                try:
                    val = qset.get(**manager.core_filters)
                except rel_model.DoesNotExist:
                    val = None

            self.set_file_value(instance, file_val, obj=val)
            setattr(instance, self.field.get_cache_name(), val)
        return instance.__dict__[self.file_field.name]

    def set_file_value(self, instance, value, obj=None):
        # Sort out what to do with the file_val
        # For reference, see django.db.models.fields.files.FileDescriptor, upon
        # which this logic is based.

        # If this value is a string (instance.file = "path/to/file") or None
        # then we simply wrap it with the appropriate attribute class according
        # to the file field. [This is FieldFile for FileFields and
        # ImageFieldFile for ImageFields; it's also conceivable that user
        # subclasses might also want to subclass the attribute class]. This
        # object understands how to convert a path to a file, and also how to
        # handle None.
        attr_cls = self.file_field.attr_class

        # Because of the (some would say boneheaded) way pickle works,
        # the underlying FieldFile might not actually itself have an associated
        # file. So we need to reset the details of the FieldFile in those cases.
        if isinstance(value, attr_cls):
            value.instance = instance
            value.field = self.file_field
            value.storage = self.file_field.storage
            value.related_object = obj
            instance.__dict__[self.file_field.name] = value
            return

        if isinstance(obj, compat_rel_to(self.field)):
            value = getattr(obj, self.field.rel_file_field_name)
        elif isinstance(value, compat_rel_to(self.field)):
            obj = value
            value = getattr(obj, self.field.rel_file_field_name)

        if isinstance(value, six.string_types) or value is None:
            attr = attr_cls(instance, self.file_field, value)
            attr.related_object = obj
            instance.__dict__[self.file_field.name] = attr

        # Other types of files may be assigned as well, but they need to have
        # the correct FieldFile interface added to them. Thus, we wrap any
        # other type of File inside a FieldFile (well, the field's attr_class,
        #  which is usually FieldFile).
        elif isinstance(value, File):
            file_copy = attr_cls(instance, self.file_field, value.name)
            if isinstance(value, FieldFile):
                # Avoid unnecessary IO caused by accessing ``value.file``
                if value and getattr(value, '_file', None):
                    file_copy.file = value.file
                file_copy._committed = value._committed
            else:
                file_copy.file = value
                file_copy._committed = False
            file_copy.related_object = obj
            instance.__dict__[self.file_field.name] = file_copy

    def __set__(self, instance, value):
        if instance is None:
            raise AttributeError("Manager must be accessed via instance")

        if isinstance(value, compat_rel_to(self.field)) or value is None:
            setattr(instance, self.field.get_cache_name(), value)

        if self.is_file_field:
            self.set_file_value(instance, value)
        else:
            manager = self.__get__(instance)
            manager.clear()
            if value is None:
                return
            if isinstance(value, compat_rel_to(self.field)):
                rel_obj_file = getattr(value, self.field.rel_file_field_name)
                file_val = rel_obj_file.path if rel_obj_file else None
                setattr(instance, self.field.file_field_name, file_val)
                manager.add(value)
            else:
                for obj in value:
                    field_value = getattr(obj, self.field.file_field_name)
                    file_val = field_value.path if field_value else None
                    setattr(instance, self.field.file_field_name, file_val)
                    manager.add(obj)
                    setattr(instance, self.field.get_cache_name(), value)


def create_generic_related_manager(superclass):
    """
    Factory function for a manager that subclasses 'superclass' (which is a
    Manager) and adds behavior for generic related objects.
    """

    class GenericRelatedObjectManager(superclass):

        def __init__(self, model=None, instance=None, symmetrical=None,
                     source_col_name=None, target_col_name=None, content_type=None,
                     content_type_field_name=None, object_id_field_name=None,
                     prefetch_cache_name=None,
                     field_identifier_field_name=None, **kwargs):
            super(GenericRelatedObjectManager, self).__init__()
            self.model = model
            self.content_type = content_type
            self.symmetrical = symmetrical
            self.instance = instance
            self._field = kwargs.pop('field', None)
            self.file_field_name = self._field.file_field_name
            self.core_filters = {
                '%s__pk' % content_type_field_name: content_type.id,
                '%s__exact' % object_id_field_name: instance._get_pk_val(),
            }
            if field_identifier_field_name:
                self.core_filters['%s__exact' % field_identifier_field_name] = getattr(self._field, field_identifier_field_name)

            self.prefetch_cache_name = prefetch_cache_name
            self.source_col_name = source_col_name
            self.target_col_name = target_col_name
            self.content_type_field_name = content_type_field_name
            self.object_id_field_name = object_id_field_name
            self.pk_val = self.instance._get_pk_val()

        def get_queryset(self):
            try:
                return self.instance._prefetched_objects_cache[self.prefetch_cache_name]
            except (AttributeError, KeyError):
                pass
            db = self._db or router.db_for_read(self.model, instance=self.instance)
            query = {
                ('%s__pk' % self.content_type_field_name): self.content_type.id,
                ('%s__exact' % self.object_id_field_name): self.pk_val,
            }
            if django.VERSION < (1, 6):
                return superclass.get_query_set(self).using(db).filter(**query)
            else:
                return superclass.get_queryset(self).using(db).filter(**query)

        if django.VERSION < (1, 6):
            get_query_set = get_queryset

        def get_prefetch_queryset(self, instances, queryset=None):
            db = self._db or router.db_for_read(self.model, instance=instances[0])
            query = {
                ('%s__pk' % self.content_type_field_name): self.content_type.id,
                ('%s__in' % self.object_id_field_name): set(obj._get_pk_val() for obj in instances),
            }
            if django.VERSION < (1, 6):
                qs = super(GenericRelatedObjectManager, self).get_query_set()
            else:
                qs = super(GenericRelatedObjectManager, self).get_queryset()
            return (qs.using(db).filter(**query),
                    operator.attrgetter(self.object_id_field_name),
                    lambda obj: obj._get_pk_val(),
                    False,
                    self.prefetch_cache_name)

        if django.VERSION < (1, 7):
            get_prefetch_query_set = get_prefetch_queryset

        def add(self, *objs):
            for obj in objs:
                if not isinstance(obj, self.model):
                    raise TypeError("'%s' instance expected" % self.model._meta.object_name)
                setattr(obj, self.content_type_field_name, self.content_type)
                setattr(obj, self.object_id_field_name, self.pk_val)
                obj.save()
                related_obj = self.__get_related_obj()
                setattr(related_obj, self.file_field_name, obj.path)
        add.alters_data = True

        @property
        def field(self):
            related_obj = self.__get_related_obj()
            return related_obj._meta.get_field(self.file_field_name)

        def __get_related_obj(self):
            related_cls = self.content_type.model_class()
            related_obj = related_cls.objects.get(pk=self.pk_val)
            return related_obj

        def remove(self, *objs):
            db = router.db_for_write(self.model, instance=self.instance)
            for obj in objs:
                obj.delete(using=db)
            try:
                related_obj = self.__get_related_obj()
            except ObjectDoesNotExist:
                pass
            else:
                setattr(related_obj, self.file_field_name, None)
        remove.alters_data = True

        def clear(self):
            db = router.db_for_write(self.model, instance=self.instance)
            for obj in self.all():
                obj.delete(using=db)
            related_obj = self.__get_related_obj()
            setattr(related_obj, self.file_field_name, None)
        clear.alters_data = True

        def create(self, **kwargs):
            kwargs[self.content_type_field_name] = self.content_type
            kwargs[self.object_id_field_name] = self.pk_val
            db = router.db_for_write(self.model, instance=self.instance)
            super_ = super(GenericRelatedObjectManager, self).using(db)
            new_obj = super_.create(**kwargs)
            if new_obj.path:
                related_obj = self.__get_related_obj()
                setattr(related_obj, self.file_field_name, new_obj.path)
            return new_obj
        create.alters_data = True

    return GenericRelatedObjectManager


try:
    from south.modelsinspector import add_introspection_rules
except ImportError:
    pass
else:
    add_introspection_rules(rules=[
        (
            (GenericForeignFileField,),
            [],
            {
                "to": ["rel.to", {}],
                "symmetrical": ["rel.symmetrical", {"default": True}],
                "object_id_field": ["object_id_field_name", {"default": "object_id"}],
                "content_type_field": ["content_type_field_name", {"default": "content_type"}],
                "blank": ["blank", {"default": True}],
            },
        ),
    ], patterns=["^generic_plus\.fields\.GenericForeignFileField"])
