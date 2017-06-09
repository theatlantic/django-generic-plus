import django
from django import forms
from django.contrib.contenttypes.models import ContentType
from django.forms import ValidationError
from django.db import models
from django.forms.models import ModelChoiceIterator
from django.utils.encoding import smart_text

from .widgets import ContentObjectSelect


class ContentObjectChoiceIterator(ModelChoiceIterator):

    def __iter__(self):
        if self.field.empty_label is not None:
            yield ("", self.field.empty_label)
        for ct_choice in self.field.ct_choices:
            choice = self.choice(ct_choice)
            if choice:
                yield choice

    def __len__(self):
        return len(list(self))

    def choice(self, choice):
        fake_field = type("Field", (object,), {
            "empty_label": None,
            "queryset": choice.get_queryset(),
            "prepare_value": self.field.prepare_value,
            "label_from_instance": staticmethod(smart_text),
            "cache_choices": False,
        })
        sub_choices = list(ModelChoiceIterator(fake_field))
        if sub_choices:
            return (choice.label, sub_choices)


class ContentObjectChoiceField(forms.ModelChoiceField):

    widget = ContentObjectSelect

    def __init__(self, *args, **kwargs):
        self.ct_choices = kwargs.pop('ct_choices')
        self.field = kwargs.pop('db_field')
        # queryset has to be here, but it doesn't have any effect
        kwargs['queryset'] = self.field.model._default_manager.none()
        super(ContentObjectChoiceField, self).__init__(*args, **kwargs)

    def prepare_value(self, value):
        ctype_kwargs = {}
        if django.VERSION > (1, 6):
            ctype_kwargs['for_concrete_model'] = self.field.for_concrete_model
        if isinstance(value, models.Model):
            ctype = ContentType.objects.get_for_model(
                type(value), **ctype_kwargs)
            object_id = value.pk
            return "%s-%s" % (ctype.pk, object_id)
        else:
            return super(ContentObjectChoiceField, self).prepare_value(value)

    def to_python(self, value):
        if value in self.empty_values:
            return None
        try:
            ctype_id, object_id = value.split('-')
            ctype_id = int(ctype_id)
        except ValueError:
            raise ValidationError(self.error_messages['invalid_choice'], code='invalid_choice')

        ctype = ContentType.objects.get_for_id(ctype_id)
        model = ctype.model_class()
        try:
            return ctype.get_object_for_this_type(pk=object_id)
        except (ValueError, TypeError, model.DoesNotExist):
            raise ValidationError(self.error_messages['invalid_choice'], code='invalid_choice')

    @property
    def choices(self):
        return ContentObjectChoiceIterator(self)

    @choices.setter
    def choices(self, value):
        # no-op setter
        pass
