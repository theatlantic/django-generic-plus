from django.apps import AppConfig
from django.core import checks


class GenericPlusConfig(AppConfig):

    name = "generic_plus"
    verbose_name = "Generic Plus"

    def ready(self):
        from generic_plus.admin import (
            append_inlines_to_registered_admins, check_admins_have_inlines)
        from generic_plus.models import patch_django

        # A no-op: generic_plus.models patches Django as it is imported, which
        # apps.populate() does before it calls any ready(). This is here so
        # that the patches are installed even if something has kept
        # generic_plus.models from being imported.
        patch_django()

        append_inlines_to_registered_admins()
        checks.register(check_admins_have_inlines)
