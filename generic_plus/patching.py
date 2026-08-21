"""
A minimal replacement for the ``monkeybiz.patch`` decorator.

Usage::

    @patch([ClassA, ClassB])
    def method_name(old_func, self, *args, **kwargs):
        ...
        return old_func(self, *args, **kwargs)

The decorated function receives the original (unbound) function as its first
argument, followed by the instance and the call's own arguments. The name of
the decorated function determines the attribute being replaced, unless ``name``
is passed explicitly.
"""
import functools


__all__ = ('patch', 'ORIGINAL_ATTR')


ORIGINAL_ATTR = '_generic_plus_patched_original'


def _make_wrapper(func, original):
    @functools.wraps(original)
    def wrapper(self, *args, **kwargs):
        return func(original, self, *args, **kwargs)

    setattr(wrapper, ORIGINAL_ATTR, original)
    return wrapper


def patch(target, name=None):
    """Replace an attribute on one or more classes with a wrapper around it."""
    classes = list(target) if isinstance(target, (list, tuple, set)) else [target]

    def decorator(func):
        attr_name = name or func.__name__
        for cls in classes:
            installed = cls.__dict__.get(attr_name)
            original = getattr(installed, ORIGINAL_ATTR, None)
            if original is None:
                original = getattr(cls, attr_name)
            setattr(cls, attr_name, _make_wrapper(func, original))
        return func

    return decorator
