import collections
from .utils import monkeypatch


def patch_django():
    patch_model_form()
    patch_model_admin()


def patch_model_form():
    from django.forms import BaseForm
    from django.forms.forms import BoundField
    from generic_plus.forms import GenericForeignFileFormField, GenericForeignFileBoundField

    @monkeypatch(BaseForm)
    def __getitem__(old_func, self, name):
        """
        Returns a GenericForeignFileBoundField instead of BoundField for GenericForeignFileFormFields
        """
        try:
            field = self.fields[name]
        except KeyError:
            raise KeyError('Key %r not found in Form' % name)
        if isinstance(field, GenericForeignFileFormField):
            return GenericForeignFileBoundField(self, field, name)
        else:
            return BoundField(self, field, name)

    # Patch to form_utils, if installed
    try:
        import form_utils.forms
    except ImportError:
        pass
    else:
        @monkeypatch(form_utils.forms.FieldsetCollection)
        def _gather_fieldsets(old_func, self):
            if not self.fieldsets:
                self.fieldsets = (('main', {
                    'fields': self.form.fields.keys(),
                    'legend': '',
                }),)
            for name, options in self.fieldsets:
                if 'fields' not in options:
                    raise ValueError("Fieldset definition must include 'fields' option." )
                boundfields = []
                for name in options['fields']:
                    if name not in self.form.fields:
                        continue
                    field = self.form.fields[name]
                    if isinstance(field, GenericForeignFileFormField):
                        bf = GenericForeignFileBoundField(self.form, field, name)
                    else:
                        bf = BoundField(self.form, field, name)
                    boundfields.append(bf)

                self._cached_fieldsets.append(
                    form_utils.forms.Fieldset(self.form, name, boundfields,
                        legend=options.get('legend', None), 
                        classes=' '.join(options.get('classes', ())),
                        description=options.get('description', '')))

def patch_model_admin(BaseModelAdmin=None, ModelAdmin=None, InlineModelAdmin=None):
    from generic_plus.fields import GenericForeignFileField

    if not BaseModelAdmin:
        from django.contrib.admin.options import BaseModelAdmin
    if not ModelAdmin:
        from django.contrib.admin.options import ModelAdmin
    if not InlineModelAdmin:
        from django.contrib.admin.options import InlineModelAdmin

    def get_generic_fk_file_fields_for_model(model):
        """Returns a list of GenericForeignFileFields on a given model"""
        opts = model._meta
        return [f for f, m in opts.get_m2m_with_model() if isinstance(f, GenericForeignFileField)]

    @monkeypatch([ModelAdmin, InlineModelAdmin])
    def __init__(old_init, self, *args, **kwargs):
        if isinstance(self, ModelAdmin):
            model, admin_site = (args + (None, None))[0:2]
            if not model:
                model = kwargs.get('model')
        else:
            model = self.model

        generic_fk_fields = get_generic_fk_file_fields_for_model(model)
        if len(generic_fk_fields):
            # ModelAdmin.inlines is defined as a mutable on that
            # class, so we need to copy it before we append.
            # (otherwise we'll modify the `inlines` attribute for
            # all ModelAdmins).
            inlines = getattr(self, 'inlines', [])
            if isinstance(inlines, collections.MutableSequence):
                self.inlines = list(inlines)
            else:
                self.inlines = []
        for field in generic_fk_fields:
            InlineFormSet = field.get_inline_admin_formset()
            self.inlines.append(InlineFormSet)

        old_init(self, *args, **kwargs)

    @monkeypatch(BaseModelAdmin)
    def formfield_for_dbfield(old_func, self, db_field, **kwargs):
        if isinstance(db_field, GenericForeignFileField):
            return db_field.formfield(parent_admin=self, **kwargs)
        return old_func(self, db_field, **kwargs)
