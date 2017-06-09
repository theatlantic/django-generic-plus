import django
from django.db import models
from django.utils.functional import cached_property
from django.utils import six

from .forms import ContentObjectChoiceField

try:
    from django.contrib.contenttypes.fields import GenericForeignKey
except ImportError:
    from django.contrib.contenttypes.generic import GenericForeignKey

try:
    from django.apps import apps
except ImportError:
    from django.db.models import get_model
else:
    get_model = apps.get_model

try:
    from django.utils.deconstruct import deconstructible
except ImportError:
    def deconstructible(f):
        return f


@deconstructible
class ContentTypeChoice(object):

    def __init__(self, to, label, limit_choices_to=None):
        self.to = to
        self.label = label
        self.limit_choices_to = limit_choices_to

    @cached_property
    def model(self):
        return get_model(self.to)

    def get_queryset(self):
        qset = self.model.objects.all()
        if self.limit_choices_to:
            limit_choices_to = self.limit_choices_to
            if six.callable(self.limit_choices_to):
                limit_choices_to = limit_choices_to()
            if isinstance(limit_choices_to, models.QuerySet):
                return limit_choices_to
            qset = qset.complex_filter(limit_choices_to)
        return qset

    def __eq__(self, other):
        if not isinstance(other, ContentTypeChoice):
            return False
        for attr in ('to', 'label', 'limit_choices_to'):
            if getattr(self, attr) != getattr(other, attr):
                return False
        return True


class GenericChoiceForeignKey(GenericForeignKey, models.Field):

    def __init__(self, ct_field='content_type', fk_field='object_id',
            for_concrete_model=True, ct_choices=None, **kwargs):
        self.ct_field = ct_field
        self.fk_field = fk_field
        self.for_concrete_model = for_concrete_model
        self.ct_choices = ct_choices
        self.editable = True
        if django.VERSION < (1, 9):
            self.rel = None
        self.column = None
        models.Field.__init__(self, **kwargs)

    @property
    def attname(self):
        return self.name

    def formfield(self, **kwargs):
        defaults = {
            'form_class': ContentObjectChoiceField,
            'ct_choices': self.ct_choices,
            'db_field': self,
        }
        defaults.update(kwargs)
        return super(GenericChoiceForeignKey, self).formfield(**defaults)
