import os
import shutil

from django import test
from django.conf import settings

from .models import TestGenericPlusModel, TestM2M, TestFileModel


DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')


class TestModels(test.TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestModels, cls).setUpClass()
        shutil.copytree(DATA_DIR, os.path.join(settings.MEDIA_ROOT, 'test'))

    def test_query(self):
        fm_a = TestFileModel.objects.create(
            content_object=TestGenericPlusModel.objects.create(
                slug='gp-a', test_file="test/foo.txt"),
            file='test/foo.txt')
        qset = TestGenericPlusModel.objects.filter(test_file="test/foo.txt")
        self.assertEqual(len(qset), 1)
        self.assertEqual(qset[0].test_file.related_object, fm_a)

    def test_blank_query(self):
        a = TestGenericPlusModel.objects.create(slug="a", test_file="")
        qset = TestGenericPlusModel.objects.filter(test_file="")
        self.assertEqual(len(qset), 1)
        self.assertEqual(qset[0], a)

    def test_prefetch_related(self):
        TestFileModel.objects.create(
            content_object=TestGenericPlusModel.objects.create(
                slug='gp-a', test_file="test/foo.txt"),
            file='test/foo.txt')
        TestFileModel.objects.create(
            content_object=TestGenericPlusModel.objects.create(
                slug='gp-b', test_file="test/bar.txt"),
            file='test/bar.txt')

        qset = TestGenericPlusModel.objects.filter(slug__in=['gp-a', 'gp-b'])
        with self.assertNumQueries(2):
            for item in qset.prefetch_related('test_file'):
                item.test_file.related_object

    def test_prefetch_related_with_m2m(self):
        fm_a = TestFileModel.objects.create(
            content_object=TestGenericPlusModel.objects.create(
                slug='gp-a', test_file="test/foo.txt"),
            file='test/foo.txt')
        fm_b = TestFileModel.objects.create(
            content_object=TestGenericPlusModel.objects.create(
                slug='gp-b', test_file="test/bar.txt"),
            file='test/bar.txt')

        for i in range(1, 4):
            fm_a.m2m.add(TestM2M.objects.create(slug='m2m-a%d' % i))
        fm_b.m2m.add(TestM2M.objects.create(slug='m2m-b1'))

        qset = TestGenericPlusModel.objects.filter(slug__in=['gp-a', 'gp-b'])
        with self.assertNumQueries(3):
            for item in qset.prefetch_related('test_file__m2m'):
                num = len(item.test_file.related_object.m2m.all())
                expected_num = 3 if item.slug == 'gp-a' else 1
                self.assertEqual(num, expected_num,
                    "Incorrect number of items (expected %d) returned for m2m of %s" %
                        (expected_num, item.slug))
