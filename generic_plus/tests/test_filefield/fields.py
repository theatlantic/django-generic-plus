from django import forms

from generic_plus.fields import GenericForeignFileField


class TestField(GenericForeignFileField):

    field_identifier_field_name = "field_identifier"

    def __init__(self, to="generic_plus.TestFileModel", *args, **kwargs):
        super(TestField, self).__init__(to, *args, **kwargs)

    def get_inline_admin_formset(self, **kwargs):
        kwargs['form_attrs'] = {
            self.rel_file_field_name: forms.FileField(required=False),
        }
        return super(TestField, self).get_inline_admin_formset(**kwargs)
