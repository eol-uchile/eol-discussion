#!/usr/bin/env python
""" Setup to allow pip installs of eol discussion xblock """

import os

from setuptools import setup, find_packages


def package_data(pkg, roots):
    """Generic function to find package_data.

    All of the files under each of the `roots` will be declared as package
    data for package `pkg`.

    """
    data = []
    for root in roots:
        for dirname, _, files in os.walk(os.path.join(pkg, root)):
            for fname in files:
                data.append(os.path.relpath(os.path.join(dirname, fname), pkg))

    return {pkg: data}


setup(
    name='eoldiscussion-xblock',
    version='1.0.1',
    description='EOL Discussion Xblock',
    author="Oficina EOL UChile",
    author_email="eol-ing@uchile.cl",
    license='AGPL v3',
    packages=find_packages(),
    include_package_data=True,
    install_requires=['XBlock'],
    entry_points={
        'xblock.v1': [
            'eoldiscussion = eoldiscussion:EolDiscussionXBlock',
        ],
    },
    package_data={"eoldiscussion": ["*.html","*.underscore"]}
)
