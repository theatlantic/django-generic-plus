from generic_plus.tests.settings import *  # noqa: F401,F403
from generic_plus.tests.settings import INSTALLED_APPS


INSTALLED_APPS = INSTALLED_APPS + ('nested_admin', 'generic_plus.tests.nested_app')
