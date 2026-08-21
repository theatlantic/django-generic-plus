from django import forms, test

from generic_plus.forms import GenericForeignFileFormField
from generic_plus.forms.widgets import (
    GenericForeignFileWidget, generic_fk_file_widget_factory)

from .test_filefield.models import TestGenericPlusModel


class TestWidgetFactory(test.SimpleTestCase):

    def setUp(self):
        self.db_field = TestGenericPlusModel._meta.get_field('test_file')
        self.related = self.db_field.remote_field

    def test_factory_sets_the_relation_attributes(self):
        widget_cls = generic_fk_file_widget_factory(related=self.related)
        self.assertIs(widget_cls.related, self.related)
        self.assertIs(widget_cls.parent_model, self.related.model)
        self.assertIs(widget_cls.rel_field, self.related.field)
        self.assertEqual(widget_cls.__module__, GenericForeignFileWidget.__module__)

    def test_attrs_win_over_the_defaults(self):
        sentinel = object()
        widget_cls = generic_fk_file_widget_factory(
            related=self.related, parent_model=sentinel, sizes=[1, 2])
        self.assertIs(widget_cls.parent_model, sentinel)
        self.assertEqual(widget_cls.sizes, [1, 2])

    def test_factory_subclasses_the_widget_class_it_is_given(self):
        class CustomWidget(GenericForeignFileWidget):
            pass

        widget_cls = generic_fk_file_widget_factory(CustomWidget, related=self.related)
        self.assertTrue(issubclass(widget_cls, CustomWidget))


class TestFormFieldWidgetArgument(test.SimpleTestCase):

    def test_widget_class_is_instantiated_with_the_form_field(self):
        class CustomWidget(GenericForeignFileWidget):
            pass

        formfield = GenericForeignFileFormField(widget=CustomWidget)
        self.assertIsInstance(formfield.widget, CustomWidget)
        self.assertIs(formfield.widget.field, formfield)

    def test_unrelated_widget_class_is_replaced(self):
        formfield = GenericForeignFileFormField(widget=forms.TextInput)
        self.assertIsInstance(formfield.widget, GenericForeignFileWidget)
        self.assertIs(formfield.widget.field, formfield)

    def test_unrelated_widget_instance_is_replaced(self):
        formfield = GenericForeignFileFormField(widget=forms.TextInput())
        self.assertIsInstance(formfield.widget, GenericForeignFileWidget)

    def test_widget_instance_is_kept(self):
        widget = GenericForeignFileWidget(attrs={'class': 'kept'})
        formfield = GenericForeignFileFormField(widget=widget)
        # forms.Field.__init__ copies the widget it is handed
        self.assertIsInstance(formfield.widget, GenericForeignFileWidget)
        self.assertEqual(formfield.widget.attrs['class'], 'kept')
