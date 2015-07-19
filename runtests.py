#!/usr/bin/env python
import os
import sys


os.environ['DJANGO_SETTINGS_MODULE'] = 'generic_plus.tests.settings'


import django
from django.core.management import execute_from_command_line


# Give feedback on used versions
sys.stderr.write('Using Python version %s from %s\n' % (sys.version[:5], sys.executable))
sys.stderr.write('Using Django version %s from %s\n' % (
    django.get_version(),
    os.path.dirname(os.path.abspath(django.__file__))))

def runtests():
    argv = sys.argv[:1] + ['test', 'generic_plus', '--traceback', '--verbosity=1'] + sys.argv[1:]
    execute_from_command_line(argv)

if __name__ == '__main__':
    runtests()
