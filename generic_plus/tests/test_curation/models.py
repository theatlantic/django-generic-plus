from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.encoding import python_2_unicode_compatible

from generic_plus.curation.fields import ContentTypeChoice, GenericChoiceForeignKey


@python_2_unicode_compatible
class RelatedAbstract(models.Model):
    name = models.CharField(max_length=255)

    class Meta:
        abstract = True
        app_label = "generic_plus"
        ordering = ['name']

    def __str__(self):
        return self.name


class Foo(RelatedAbstract):

    class Meta:
        app_label = "generic_plus"


class Bar(RelatedAbstract):

    class Meta:
        app_label = "generic_plus"


class Baz(RelatedAbstract):

    class Meta:
        app_label = "generic_plus"


@python_2_unicode_compatible
class BazProxy(Baz):

    class Meta:
        app_label = "generic_plus"
        proxy = True

    def __str__(self):
        return "%s (proxy)" % self.name


class Group(models.Model):
    name = models.CharField(max_length=255)

    class Meta:
        app_label = 'generic_plus'


def limit_bar_choices():
    return ~models.Q(name='j')


class Item(models.Model):

    position = models.PositiveIntegerField()
    name = models.CharField(max_length=255)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)

    CT_CHOICES = (
        ContentTypeChoice('generic_plus.Foo', 'Foo'),
        ContentTypeChoice(
            'generic_plus.Bar', 'Bar',
            limit_choices_to=limit_bar_choices),
        ContentTypeChoice(
            'generic_plus.BazProxy', 'Baz'))

    content_type = models.ForeignKey(ContentType, blank=True, null=True, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(null=True, verbose_name=b'Id', blank=True)
    content_object = GenericChoiceForeignKey('content_type', 'object_id', for_concrete_model=False,
        ct_choices=CT_CHOICES)

    class Meta:
        app_label = 'generic_plus'
