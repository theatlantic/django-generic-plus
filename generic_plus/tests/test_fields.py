from django import test
from django.db import models

from .test_filefield.fields import TestImageField
from .test_filefield.models import TestFileModel, TestGenericPlusModel


class AbstractImageModel(models.Model):
    """
    Only used to exercise ``contribute_to_class``: abstract, so that it neither
    creates a table nor connects ImageField's post_init dimension handler.
    """

    width = models.IntegerField(null=True)
    height = models.IntegerField(null=True)
    test_image = TestImageField(upload_to="test", width_field="width", height_field="height")

    class Meta:
        abstract = True
        app_label = "generic_plus"


class AbstractImageModelWithoutDimensions(models.Model):

    test_image = TestImageField(upload_to="test")

    class Meta:
        abstract = True
        app_label = "generic_plus"


class InheritedImageModel(AbstractImageModelWithoutDimensions):
    """Inheritance runs contribute_to_class() a second time for test_image."""

    class Meta:
        abstract = True
        app_label = "generic_plus"


class TestFileFieldKwargs(test.SimpleTestCase):

    def test_width_and_height_reach_an_image_file_field(self):
        field = AbstractImageModel.test_image
        self.assertEqual(field.file_kwargs['width_field'], 'width')
        self.assertEqual(field.file_kwargs['height_field'], 'height')
        self.assertEqual(field.file_field.width_field, 'width')
        self.assertEqual(field.file_field.height_field, 'height')

    def test_unset_width_and_height_are_dropped_for_an_image_file_field(self):
        field = AbstractImageModelWithoutDimensions.test_image
        self.assertNotIn('width_field', field.file_kwargs)
        self.assertNotIn('height_field', field.file_kwargs)
        self.assertIsNone(field.file_field.width_field)

    def test_inherited_image_file_field(self):
        field = InheritedImageModel.test_image
        self.assertNotIn('width_field', field.file_kwargs)
        self.assertIsNone(field.file_field.width_field)

    def test_width_and_height_are_dropped_for_a_plain_file_field(self):
        field = TestGenericPlusModel._meta.get_field('test_file')
        self.assertNotIn('width_field', field.file_kwargs)
        self.assertNotIn('height_field', field.file_kwargs)


class TestGenericRelatedObjectManager(test.TestCase):
    """
    add()/create() read the file name off the generic related object's own file
    field, named by ``rel_file_field_name``.
    """

    def setUp(self):
        self.instance = TestGenericPlusModel.objects.create(slug='gp-a')

    def test_add(self):
        obj = TestFileModel(file='test/foo.txt')
        self.instance.test_file_generic_rel.add(obj)
        self.assertEqual(obj.object_id, self.instance.pk)
        self.assertEqual(
            [o.pk for o in self.instance.test_file_generic_rel.all()], [obj.pk])
        instance = TestGenericPlusModel.objects.get(pk=self.instance.pk)
        self.assertEqual(instance.test_file.related_object, obj)

    def test_add_without_a_file(self):
        obj = TestFileModel(file='')
        self.instance.test_file_generic_rel.add(obj)
        self.assertEqual(obj.object_id, self.instance.pk)

    def test_create(self):
        obj = self.instance.test_file_generic_rel.create(file='test/bar.txt')
        self.assertEqual(obj.object_id, self.instance.pk)
        self.assertEqual(
            [o.pk for o in self.instance.test_file_generic_rel.all()], [obj.pk])

    def test_remove(self):
        obj = TestFileModel.objects.create(
            content_object=self.instance, file='test/foo.txt')
        self.instance.test_file_generic_rel.remove(obj)
        self.assertEqual(list(self.instance.test_file_generic_rel.all()), [])

    def test_clear(self):
        TestFileModel.objects.create(content_object=self.instance, file='test/foo.txt')
        self.instance.test_file_generic_rel.clear()
        self.assertEqual(list(self.instance.test_file_generic_rel.all()), [])


class TestGenericRelDescriptorSet(test.TestCase):
    """
    Direct assignment to ``<field>_generic_rel`` raises TypeError, matching
    Django's own related managers. Rows are managed through the manager's
    add(), remove() and clear() methods, or by assigning to the file field;
    a refused assignment leaves the existing rows untouched.
    """

    def setUp(self):
        self.instance = TestGenericPlusModel.objects.create(slug='gp-assign')

    def test_assigning_a_related_object_is_prohibited(self):
        obj = TestFileModel.objects.create(
            content_object=self.instance, file='test/foo.txt')
        with self.assertRaisesMessage(
                TypeError, "Direct assignment to 'test_file_generic_rel'"):
            self.instance.test_file_generic_rel = obj

    def test_assigning_a_list_is_prohibited(self):
        obj = TestFileModel.objects.create(
            content_object=self.instance, file='test/bar.txt')
        with self.assertRaisesMessage(
                TypeError, "Direct assignment to 'test_file_generic_rel'"):
            self.instance.test_file_generic_rel = [obj]

    def test_assigning_none_is_prohibited(self):
        with self.assertRaisesMessage(
                TypeError, "Direct assignment to 'test_file_generic_rel'"):
            self.instance.test_file_generic_rel = None

    def test_the_error_names_the_alternatives(self):
        with self.assertRaisesMessage(TypeError, "add(), remove(), or clear()"):
            self.instance.test_file_generic_rel = None

    def test_assignment_has_no_side_effects(self):
        obj = TestFileModel.objects.create(
            content_object=self.instance, file='test/foo.txt')
        with self.assertRaises(TypeError):
            self.instance.test_file_generic_rel = None
        self.assertEqual(
            [o.pk for o in self.instance.test_file_generic_rel.all()], [obj.pk])
