from generic_plus.patching import patch


_patched = False


def patch_django():
    """Install the generic-plus monkeypatches. Safe to call more than once."""
    global _patched

    if _patched:
        return

    patch_model_form()
    patch_model_admin()

    _patched = True


def patch_model_form():
    try:
        import form_utils.forms
    except ImportError:
        return

    from django.forms.boundfield import BoundField
    from generic_plus.forms import GenericForeignFileFormField, GenericForeignFileBoundField

    @patch(form_utils.forms.FieldsetCollection)
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
    from generic_plus.admin import (
        append_generic_file_inlines, filter_generic_file_inlines)
    from generic_plus.fields import GenericForeignFileField

    if not BaseModelAdmin:
        from django.contrib.admin.options import BaseModelAdmin
    if not ModelAdmin:
        from django.contrib.admin.options import ModelAdmin
    if not InlineModelAdmin:
        from django.contrib.admin.options import InlineModelAdmin

    # The inline is appended at construction time because django-nested-admin
    # reads ``self.inlines`` when it builds its inline tree.
    @patch([ModelAdmin, InlineModelAdmin])
    def __init__(old_init, self, *args, **kwargs):
        if isinstance(self, ModelAdmin):
            model, admin_site = (args + (None, None))[0:2]
            if not model:
                model = kwargs.get('model')
        else:
            model = self.model

        append_generic_file_inlines(self, model)

        old_init(self, *args, **kwargs)

    @patch(ModelAdmin)
    def get_inline_instances(old_func, self, request, obj=None):
        args = [obj] if obj else []
        inline_instances = old_func(self, request, *args)
        return filter_generic_file_inlines(self, request, obj, inline_instances)

    @patch(BaseModelAdmin)
    def formfield_for_dbfield(old_func, self, db_field, **kwargs):
        if isinstance(db_field, GenericForeignFileField):
            return db_field.formfield(parent_admin=self, **kwargs)
        return old_func(self, db_field, **kwargs)


# django-nested-admin copies ModelAdmin.get_inline_instances into the body of
# NestedInlineModelAdminMixin, a plain mixin, when nested_admin.nested is
# imported. That import happens from a project's admin module, i.e. during
# django.contrib.admin's autodiscover(), and django.contrib.admin precedes
# generic_plus in INSTALLED_APPS in every known deployment, so its ready()
# runs first. Patching from GenericPlusConfig.ready() would therefore leave
# nested inlines with a copy of the unpatched function, and their generic-plus
# inlines would not be filtered out of admins that omit the field from their
# fieldsets (ManagementForm validation errors on save).
patch_django()
