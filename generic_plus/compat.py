import django


dj19 = bool(django.VERSION >= (1, 9))


def compat_rel(f):
    return getattr(f, 'remote_field' if dj19 else 'rel')


def compat_rel_to(f):
    return getattr(compat_rel(f), 'model' if dj19 else 'to')
