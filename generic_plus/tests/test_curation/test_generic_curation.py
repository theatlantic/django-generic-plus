from unittest import SkipTest

import django
from django.test import TestCase, RequestFactory
from django.test.utils import override_settings
from django.contrib.contenttypes.models import ContentType

try:
    from django.urls import reverse
except ImportError:
    from django.core.urlresolvers import reverse

from .models import Foo, Bar, BazProxy, Item, Group
from ..settings import INSTALLED_APPS

import lxml.html

try:
    from django.contrib.auth import get_user_model
except ImportError:
    from django.contrib.auth.models import User

    def get_user_model():
        return User


class TestModels(TestCase):

    available_apps = [a for a in INSTALLED_APPS]

    @classmethod
    def setUpClass(cls):
        super(TestModels, cls).setUpClass()
        if django.VERSION < (1, 8):
            raise SkipTest("Not supported in django < 1.8")

    def test_create(self):
        foo = Foo.objects.create(name="a1")
        group = Group.objects.create(name='A')
        item = Item.objects.create(
            group=group,
            content_object=foo,
            position=0,
            name="A-a1")
        foo_ctype = ContentType.objects.get_for_model(Foo)
        self.assertEqual(item.content_type, foo_ctype)
        self.assertEqual(item.object_id, foo.pk)
        self.assertEqual(item.content_object, foo)


@override_settings(ROOT_URLCONF='generic_plus.tests.test_curation.urls')
class TestAdmin(TestCase):

    available_apps = [a for a in INSTALLED_APPS]
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super(TestAdmin, cls).setUpClass()
        if django.VERSION < (1, 8):
            raise SkipTest("Not supported in django < 1.8")

    def setUp(self):
        super(TestAdmin, self).setUp()
        User = get_user_model()
        self.user = User.objects.create_superuser(
            username='test',
            email='test@example.com',
            password='test')
        self.client.login(username="test", password="test")
        instance_names = [('a', 'b', 'c'), ('i', 'j', 'k'), ('x', 'y', 'z')]
        for names, model_cls in zip(instance_names, [Foo, Bar, BazProxy]):
            for name in names:
                model_cls.objects.create(name=name)

    def test_add_form_loads(self):
        """The add form view for a lockable object should load with status 200"""
        url = reverse('admin:generic_plus_group_add')
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_add_form_save(self):
        url = reverse('admin:generic_plus_group_add')
        foo = Foo.objects.get(name="a")
        foo_ctype = ContentType.objects.get_for_model(Foo)
        data = {
            "item_set-TOTAL_FORMS": 1,
            "item_set-INITIAL_FORMS": 0,
            "item_set-MAX_NUM_FORMS": 0,
            "_save": "Save",
            "name": "A",
            "item_set-0-id": "",
            "item_set-0-group": "",
            "item_set-0-content_object": "%s-%s" % (foo_ctype.pk, foo.pk),
            "item_set-0-name": "A0",
            "item_set-0-position": "0",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        items = Item.objects.filter(name='A0')
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.content_object, foo)
        self.assertEqual(item.content_type, foo_ctype)
        self.assertEqual(item.object_id, foo.pk)
        self.assertEqual(item.content_object, foo)

    def test_change_form_loads(self):
        foo = Foo.objects.get(name="a")
        group = Group.objects.create(name='A')
        Item.objects.create(
            group=group,
            content_object=foo,
            position=0,
            name="A-a1")
        url = reverse('admin:generic_plus_group_change', args=[group.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        def format_opt_val(obj):
            content_type = ContentType.objects.get_for_model(
                type(obj), for_concrete_model=False)
            return "%s-%s" % (content_type.pk, obj.pk)

        objs = tuple(
            [format_opt_val(o) for o in Foo.objects.all()] +
            [format_opt_val(o) for o in Bar.objects.exclude(name='j')] +
            [format_opt_val(o) for o in BazProxy.objects.all()])

        tree = lxml.html.fromstring(response.content)
        elements = tree.xpath('//*[@name="item_set-0-content_object"]')
        self.assertNotEqual(len(elements), 0, "content_object select element not found")
        self.assertHTMLEqual(lxml.html.tostring(elements[0], encoding='unicode'), """
        <select id="id_item_set-0-content_object" name="item_set-0-content_object">
            <option value="">---------</option>
            <optgroup label="Foo">
                <option value="%s" selected="selected">a</option>
                <option value="%s">b</option>
                <option value="%s">c</option>
            </optgroup>
            <optgroup label="Bar">
                <option value="%s">i</option>
                <option value="%s">k</option>
            </optgroup>
            <optgroup label="Baz">
                <option value="%s">x (proxy)</option>
                <option value="%s">y (proxy)</option>
                <option value="%s">z (proxy)</option>
            </optgroup>
        </select>
        """ % objs)

    def test_change_form_save(self):
        foo_a = Foo.objects.get(name="a")
        baz_y = BazProxy.objects.get(name="y")
        baz_ctype = ContentType.objects.get_for_model(BazProxy, for_concrete_model=False)
        group = Group.objects.create(name='A')
        item = Item.objects.create(
            group=group,
            content_object=foo_a,
            position=0,
            name="A0")
        url = reverse('admin:generic_plus_group_change', args=[group.pk])
        data = {
            "item_set-TOTAL_FORMS": 1,
            "item_set-INITIAL_FORMS": 1,
            "item_set-MAX_NUM_FORMS": 0,
            "_save": "Save",
            "name": "A",
            "item_set-0-id": "%s" % item.pk,
            "item_set-0-group": "%s" % group.pk,
            "item_set-0-content_object": "%s-%s" % (baz_ctype.pk, baz_y.pk),
            "item_set-0-name": "A0",
            "item_set-0-position": "0",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        items = Item.objects.filter(name='A0')
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.content_object, baz_y)
        self.assertEqual(item.content_type, baz_ctype)
        self.assertEqual(item.object_id, baz_y.pk)
