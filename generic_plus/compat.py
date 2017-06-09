import django


dj19 = bool(django.VERSION >= (1, 9))


def compat_rel(f):
    if django.VERSION > (1, 9):
        rel_attr = 'remote_field'
    else:
        rel_attr = 'rel'
    return getattr(f, rel_attr, None)


def compat_rel_to(f):
    return getattr(compat_rel(f), 'model' if dj19 else 'to')
