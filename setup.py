#!/usr/bin/env python
from setuptools import setup, find_packages


setup(
    name='django-generic-plus',
    version=__import__("generic_plus").__version__,
    install_requires=[
        'python-monkey-business>=1.0.0',
    ],
    description="Django model field that combines the functionality of "
                "GenericForeignKey and FileField",
    long_description=open('README.rst').read(),
    license='BSD',
    platforms="any",
    author='The Atlantic',
    author_email='programmers@theatlantic.com',
    url='https://github.com/theatlantic/django-generic-plus',
    packages=find_packages(),
    python_requires='>=3',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Framework :: Django',
        'Framework :: Django :: 3.2',
        'Framework :: Django :: 4.0',
        'Framework :: Django :: 4.1',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
    ],
    include_package_data=True,
    zip_safe=False)
