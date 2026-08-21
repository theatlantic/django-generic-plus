from generic_plus.patching import ORIGINAL_ATTR, patch


class Base(object):

    def greet(self, name):
        return "hello %s" % name


class Other(object):

    def greet(self, name):
        return "hi %s" % name


def test_old_func_is_passed_the_original():
    class Target(Base):
        pass

    original = Target.greet

    @patch(Target)
    def greet(old_func, self, name):
        return "<%s>" % old_func(self, name)

    assert Target().greet("world") == "<hello world>"
    assert getattr(Target.greet, ORIGINAL_ATTR) is original


def test_decorator_returns_the_undecorated_function():
    class Target(Base):
        pass

    @patch(Target)
    def greet(old_func, self, name):
        return old_func(self, name)

    assert greet.__name__ == "greet"
    assert greet is not Target.greet


def test_patching_twice_does_not_double_wrap():
    class Target(Base):
        pass

    def apply():
        @patch(Target)
        def greet(old_func, self, name):
            return "<%s>" % old_func(self, name)

    apply()
    apply()

    assert Target().greet("world") == "<hello world>"


def test_multiple_classes_keep_their_own_original():
    class TargetA(Base):
        pass

    class TargetB(Other):
        pass

    @patch([TargetA, TargetB])
    def greet(old_func, self, name):
        return "<%s>" % old_func(self, name)

    assert TargetA().greet("world") == "<hello world>"
    assert TargetB().greet("world") == "<hi world>"


def test_inherited_method_is_patched_on_the_subclass_only():
    class Target(Base):
        pass

    @patch(Target)
    def greet(old_func, self, name):
        return "<%s>" % old_func(self, name)

    assert Target().greet("world") == "<hello world>"
    assert Base().greet("world") == "hello world"


def test_name_argument_overrides_the_function_name():
    class Target(Base):
        pass

    @patch(Target, name="greet")
    def something_else(old_func, self, name):
        return "<%s>" % old_func(self, name)

    assert Target().greet("world") == "<hello world>"


def test_wrapper_keeps_the_original_metadata():
    class Target(Base):
        pass

    @patch(Target)
    def greet(old_func, self, name):
        return old_func(self, name)

    assert Target.greet.__name__ == "greet"
    assert Target.greet.__doc__ == Base.greet.__doc__


def test_arguments_are_passed_through():
    class Target(object):
        def method(self, *args, **kwargs):
            return (args, kwargs)

    @patch(Target)
    def method(old_func, self, *args, **kwargs):
        return old_func(self, *args, **kwargs)

    assert Target().method(1, 2, a=3) == ((1, 2), {'a': 3})
