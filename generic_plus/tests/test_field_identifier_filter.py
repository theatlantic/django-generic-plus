from django import test

from .test_filefield.models import TestFileModel, TwoFieldGenericPlusModel


class TestFieldIdentifierFilter(test.TestCase):
    """
    Two GenericForeignFileFields on one model, distinguished only by their
    field_identifier, must not see each other's rows.
    """

    def setUp(self):
        self.instance = TwoFieldGenericPlusModel.objects.create(slug="two-fields")
        self.one = TestFileModel.objects.create(
            content_object=self.instance, file="test/foo.txt", field_identifier="one")
        self.two = TestFileModel.objects.create(
            content_object=self.instance, file="test/bar.txt", field_identifier="two")

    def test_generic_rel_manager_filters_on_field_identifier(self):
        self.assertEqual(
            [o.pk for o in self.instance.file_one_generic_rel.all()], [self.one.pk])
        self.assertEqual(
            [o.pk for o in self.instance.file_two_generic_rel.all()], [self.two.pk])

    def test_file_descriptor_returns_the_matching_related_object(self):
        instance = TwoFieldGenericPlusModel.objects.get(pk=self.instance.pk)
        self.assertEqual(instance.file_one.related_object, self.one)
        self.assertEqual(instance.file_two.related_object, self.two)

    def test_prefetch_related_filters_on_field_identifier(self):
        qset = TwoFieldGenericPlusModel.objects.filter(pk=self.instance.pk)
        for instance in qset.prefetch_related('file_one', 'file_two'):
            self.assertEqual(instance.file_one.related_object, self.one)
            self.assertEqual(instance.file_two.related_object, self.two)
