#!/bin/bash

pip install --src /openedx/venv/src -e git+https://github.com/eol-uchile/eol_forum_notifications@1.0.0#egg=eol_forum_notifications
pip install --src /openedx/venv/src -e /openedx/requirements/app
pip install pytest-cov genbadge[coverage]

cd /openedx/requirements/app

mkdir test_root
ln -s /openedx/staticfiles ./test_root/

cd /openedx/requirements/app

DJANGO_SETTINGS_MODULE=lms.envs.test EDXAPP_TEST_MONGO_HOST=mongodb pytest eoldiscussion/tests.py
  
rm -rf test_root

genbadge coverage
