import django
from django.contrib.contenttypes.models import ContentType
from django.db import models

try:
    from django.contrib.contenttypes.fields import GenericForeignKey
except ImportError:
    from django.contrib.contenttypes.generic import GenericForeignKey

from .fields import TestField


class TestM2M(models.Model):

    slug = models.SlugField()

    class Meta:
        app_label = "generic_plus"


class TestRelated(models.Model):

    slug = models.SlugField()

    class Meta:
        app_label = "generic_plus"


class TestFileModel(models.Model):

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    field_identifier = models.SlugField(null=False, blank=True, default="")

    file = models.FileField(upload_to="test")
    description = models.TextField(blank=True)

    related = models.ForeignKey(TestRelated, null=True, blank=True,
        on_delete=models.CASCADE)
    m2m = models.ManyToManyField(TestM2M, blank=True)

    class Meta:
        app_label = "generic_plus"

    def save(self, **kwargs):
        super(TestFileModel, self).save(**kwargs)
        model_class = self.content_type.model_class()

        if django.VERSION >= (1, 8):
            fields_with_models = [
                (f, f.model if f.model != model_class else None)
                for f in model_class._meta.get_fields()
                if not f.is_relation
                    or f.one_to_one
                    or (f.many_to_one and f.related_model)
            ]
        else:
            fields_with_models = model_class._meta.get_fields_with_model()

        for field, field_model_class in fields_with_models:
            field_model_class = field_model_class or model_class
            if (isinstance(field, TestField) and field.field_identifier == self.field_identifier):
                field_model_class.objects.filter(pk=self.object_id).update(**{
                    field.attname: self.file.name or '',
                })


class TestGenericPlusModel(models.Model):

    slug = models.SlugField()
    test_file = TestField(upload_to="test")

    class Meta:
        app_label = "generic_plus"


class SecondTestGenericPlusModel(models.Model):

    slug = models.SlugField()
    test_file = TestField(upload_to="test")

    class Meta:
        app_label = "generic_plus"


class OtherGenericRelatedModel(models.Model):

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    slug = models.SlugField()

    class Meta:
        app_label = "generic_plus"
