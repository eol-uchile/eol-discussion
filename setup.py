#!/usr/bin/env python
""" Setup to allow pip installs of eol discussion xblock """

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
            'eolgradediscussion = eolgradediscussion.eolgradediscussion:EolGradeDiscussionXBlock',
        ],
        "lms.djangoapp": [
            "eoldiscussion = eoldiscussion.apps:EolDiscussionConfig"
        ],
        "cms.djangoapp": [
            "eoldiscussion = eoldiscussion.apps:EolDiscussionConfig",
        ],
    }
)
