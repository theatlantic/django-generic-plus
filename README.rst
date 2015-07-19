django-generic-plus
###################

.. image:: https://travis-ci.org/theatlantic/django-generic-plus.svg?branch=master
    :target: https://travis-ci.org/theatlantic/django-generic-plus
    :alt: Build Status

**django-generic-plus** is a python module which provides a Django model
field that combines the functionality of GenericForeignKey and FileField
into a single field.

It is useful in situations where one wishes to associate metadata with a
FileField or ImageField. It is currently used by
`django-cropduster <https://github.com/theatlantic/django-cropduster>`_.
