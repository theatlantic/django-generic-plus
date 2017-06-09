import types

from django.utils.six.moves import filter
import monkeybiz


def patch_django():
    patch_model_form()
    patch_model_admin()


def patch_model_form():
    from django.forms import BaseForm
    from django.forms.forms import BoundField
    from generic_plus.forms import GenericForeignFileFormField, GenericForeignFileBoundField

    @monkeybiz.patch(BaseForm)
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
        @monkeybiz.patch(form_utils.forms.FieldsetCollection)
        def _gather_fieldsets(old_func, self):
            if not self.fieldsets:
                self.fieldsets = (('main', {
                    'fields': self.form.fields.keys(),
                    'legend': '',
                }),)
            for name, options in self.fieldsets:
                if 'fields' not in options:
                    raise ValueError("Fieldset definition must include 'fields' option.")
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
    try:
        # Django 1.8+
        from django.contrib.admin.utils import flatten_fieldsets
    except ImportError:
        from django.contrib.admin.util import flatten_fieldsets

    if not BaseModelAdmin:
        from django.contrib.admin.options import BaseModelAdmin
    if not ModelAdmin:
        from django.contrib.admin.options import ModelAdmin
    if not InlineModelAdmin:
        from django.contrib.admin.options import InlineModelAdmin

    def get_generic_fk_file_fields_for_model(model):
        """Returns a list of GenericForeignFileFields on a given model"""
        opts = model._meta
        if hasattr(opts, 'get_fields'):
            # Django 1.8+
            m2m_fields = [f for f in opts.get_fields() if f.many_to_many and not f.auto_created]
        else:
            m2m_fields = opts.many_to_many
        if hasattr(opts, 'private_fields'):
            private_fields = opts.private_fields
        else:
            private_fields = opts.virtual_fields
        m2m_related_fields = set(m2m_fields + private_fields)
        return [f for f in m2m_related_fields if isinstance(f, GenericForeignFileField)]

    @monkeybiz.patch([ModelAdmin, InlineModelAdmin])
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
            try:
                self.inlines = list(self.inlines)
            except:
                self.inlines = []

            # Prevent duplicate inlines being added
            existing_inline_fields = filter(None, [getattr(i, 'field', None) for i in self.inlines])
            generic_fk_fields_to_add = set(generic_fk_fields) ^ set(existing_inline_fields)

            for field in generic_fk_fields_to_add:
                self.inlines.append(field.get_inline_admin_formset())

        old_init(self, *args, **kwargs)

    @monkeybiz.patch(ModelAdmin)
    def get_inline_instances(old_func, self, request, obj=None):
        """
        Skip generic-plus inlines if the field is not in fieldsets.
        Failing to do so causes ManagementForm validation errors on save.
        """
        args = [obj] if obj else []
        inline_instances = old_func(self, request, *args)
        fieldsets = flatten_fieldsets(self.get_fieldsets(request, obj=obj))

        def skip_inline_instance(inline):
            f = getattr(inline, 'field', None)
            return isinstance(f, GenericForeignFileField) and f.name not in fieldsets

        if isinstance(inline_instances, types.GeneratorType):
            return (i for i in inline_instances if not(skip_inline_instance(i)))
        else:
            return [i for i in inline_instances if not(skip_inline_instance(i))]

    @monkeybiz.patch(BaseModelAdmin)
    def formfield_for_dbfield(old_func, self, db_field, **kwargs):
        if isinstance(db_field, GenericForeignFileField):
            return db_field.formfield(parent_admin=self, **kwargs)
        return old_func(self, db_field, **kwargs)


patch_django()
