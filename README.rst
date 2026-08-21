django-generic-plus
###################

.. image:: https://github.com/theatlantic/django-generic-plus/actions/workflows/test.yml/badge.svg
    :target: https://github.com/theatlantic/django-generic-plus/actions
    :alt: Build Status

**django-generic-plus** is a python module which provides a Django model
field that combines the functionality of GenericForeignKey and FileField
into a single field.

It is useful in situations where one wishes to associate metadata with a
FileField or ImageField. It is currently used by
`django-cropduster <https://github.com/theatlantic/django-cropduster>`_.

Requirements
============

* Python 3.10+
* Django 4.2, 5.0, 5.1, or 5.2

4.0 upgrade notes
=================

There are no migrations. The changes below are the ones visible from outside
the package.

**Deleting through a generic relation is scoped to one field.**
``GenericRelatedObjectManager.get_queryset()`` filters on
``field_identifier``, so ``instance.<field>_generic_rel.all()`` returns only
that field's rows and ``clear()`` deletes only them. In 3.1.0, ``clear()``
deleted every generic row attached to the instance, whatever identifier it
carried. That is a data-loss fix, but it was also a working way to drop all
of an instance's attachments at once; code that relied on the old behavior
has to clear each field explicitly now. Audit calls to
``*_generic_rel.clear()`` before upgrading.

**Direct assignment to ``<field>_generic_rel`` raises ``TypeError``.** As
with Django's own related managers, the relation cannot be assigned to;
assign to the file field or use the manager's ``add()``, ``remove()`` and
``clear()`` methods. No working code is affected: in the assignment branch
this replaces, a multi-object assignment raised ``AttributeError`` on any
storage, a single-object assignment raised ``NotImplementedError`` on remote
storages (it read ``FieldFile.path``), and on local storage it wrote an
absolute filesystem path into a column everything else treats as a
storage-relative name.

**The widget strips ``MEDIA_ROOT`` from the file value it renders.** 3.1.0
built the pattern as ``r'^%s/?' % re.compile(settings.MEDIA_ROOT)``,
interpolating the repr of a compiled pattern, so the substitution matched
nothing. The prefix is now removed, and ``file_value`` is what the template
writes into the hidden input named after the field. A project whose file
column stores absolute paths sees both the rendered value and the value
posted back change; one storing storage-relative names sees no change.

**A custom widget's attributes are set on the instance.**
``GenericForeignFileField.formfield()`` assigns ``parent_admin``, ``request``
and ``file_field_name`` after instantiating the widget. 3.1.0 assigned them
to whatever was passed as ``widget``, so a field passing a widget *class*
through ``formfield(widget=...)`` had all three land on the class: fields
sharing that class read whichever value was written last, and a live
``WSGIRequest`` stayed pinned to the class for the worker's lifetime. A
widget subclass that reads any of the three as a class attribute must read
them off ``self``.

**``get_fieldsets()`` is called fewer times.** The patched
``get_inline_instances()`` calls it only when one of the admin's inlines
holds a ``GenericForeignFileField``, rather than on every admin on every
pass. The inlines returned are unchanged, but an admin whose
``get_fieldsets()`` or ``get_form()`` has side effects gets fewer calls, in
a different order. Relatedly, a duplicate
inline is no longer appended for a ``GenericForeignFileField`` belonging to
another model: the old selection took a symmetric difference against the
admin's existing inline fields, which picked up fields present only in that
second set.

**``generic_plus.compat`` is removed.** ``compat_rel`` and ``compat_rel_to``
raise ``ModuleNotFoundError`` on import; read ``field.remote_field`` and
``field.remote_field.model`` instead. ``python-monkey-business`` is also no
longer a dependency, and the replacement decorator uses ``functools.wraps``,
so a patched admin method reports ``__module__ ==
'django.contrib.admin.options'`` rather than ``'generic_plus.models'``. Code
that identified the patch by module name should test for the
``_generic_plus_patched_original`` attribute.
...
