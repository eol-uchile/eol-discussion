"""Setup for eolzoom XBlock."""


import os

from setuptools import setup


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

import  setuptools

setuptools.setup(
    name='eoldiscussion',
    version='1.0.0',
    description='EOL Discussion Xblock & Allows you to save forum notification and send mails with threads and/or comments unread among other things',
    author="Oficina EOL UChile",
    author_email="eol-ing@uchile.cl",
    license='AGPL v3',
    packages=setuptools.find_packages(),
    include_package_data=True,
    install_requires=['XBlock'],
    entry_points={
        'xblock.v1': [
            'eoldiscussion = eoldiscussion.eoldiscussion:EolDiscussionXBlock',
            'eolgradediscussion = eoldiscussion.eolgradediscussion:EolGradeDiscussionXBlock',
        ],
        "lms.djangoapp": [
            "eoldiscussion = eoldiscussion.apps:EolDiscussionConfig"
        ],
        "cms.djangoapp": [
            "eoldiscussion = eoldiscussion.apps:EolDiscussionConfig",
        ],
    }
)
