#!/usr/bin/env python

try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages


setup_kwargs = {}

try:
    setup_kwargs['long_description'] = open('README.rst').read()
except IOError:
    # Use the create_readme_rst command to convert README to reStructuredText
    pass


setup(
    name='django-generic-plus',
    version="1.2.7",
    install_requires=[
        'six>=1.7.0',
    ],
    description="Django model field that combines the functionality of "
                "GenericForeignKey and FileField",
    author='The Atlantic',
    author_email='programmers@theatlantic.com',
    url='https://github.com/theatlantic/django-generic-plus',
    packages=find_packages(),
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Framework :: Django',
    ],
    include_package_data=True,
    zip_safe=False,
    entry_points={
        'distutils.commands': [
            'create_readme_rst = generic_plus.build:create_readme_rst',
        ],
    },
    **setup_kwargs)
