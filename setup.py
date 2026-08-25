#!/usr/bin/env python
""" Setup to allow pip installs of eol discussion xblock """

from setuptools import setup, find_packages

setup(
    name='eoldiscussion',
    version='1.0.0',
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
            'eolgradediscussion = eolgradediscussion:EolGradeDiscussionXBlock',
        ],
        "lms.djangoapp": [
            "eoldiscussion = eoldiscussion.apps:EolDiscussionConfig",
            "eolgradediscussion = eolgradediscussion.apps:EolGradeDiscussionConfig",
        ],
        "cms.djangoapp": [
            "eoldiscussion = eoldiscussion.apps:EolDiscussionConfig",
            "eolgradediscussion = eolgradediscussion.apps:EolGradeDiscussionConfig",
        ],
    }
)
