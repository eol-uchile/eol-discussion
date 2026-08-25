#!/usr/bin/env python
# -- coding: utf-8 --

from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.contrib.sites.shortcuts import get_current_site
from django.db import transaction
from django.http import HttpResponseRedirect, HttpResponseForbidden, Http404
from django.shortcuts import render
from django.urls import reverse
from django.http import HttpResponse
import openedx.core.djangoapps.django_comment_common.comment_client as cc
from openedx.core.djangoapps.django_comment_common.utils import ThreadContext
from eol_forum_notifications.models import EolForumNotificationsUser, EolForumNotificationsDiscussions
from lms.djangoapps.courseware.courses import get_course_by_id
from openedx.core.lib.courses import course_image_url
from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore.django import modulestore
from django.utils.timezone import now
import json
import requests
import logging

logger = logging.getLogger(__name__)


def get_users_notifications(how_often, discussion_id, course_id):
    """
        return all user based on params
    """
    notifications = []
    course_key = CourseKey.from_string(course_id)
    discussion = EolForumNotificationsDiscussions.objects.get(discussion_id=discussion_id, course_id=course_key)
    if how_often == 'daily':
        if discussion.daily_threads > 0 or discussion.daily_comment > 0:
            notifications = EolForumNotificationsUser.objects.filter(
                how_often=how_often, 
                discussion__discussion_id=discussion_id, 
                discussion__course_id=course_key).values(
                    'user__id',
                    'user__email'
                )
    else:
        #weekly
        if discussion.weekly_threads > 0 or discussion.weekly_comment > 0:
            notifications = EolForumNotificationsUser.objects.filter(
                how_often=how_often, 
                discussion__discussion_id=discussion_id, 
                discussion__course_id=course_key).values(
                    'user__id',
                    'user__email'
                )
    return list(notifications)

def get_courses_onlive():
    """
        get all courses onlive (not archived)
    """
    courses = EolForumNotificationsDiscussions.objects.all().values('course_id').distinct()
    course_data = {}
    for c in courses:
        aux = get_course_by_id(c['course_id'])
        if aux.end is None or now() <= aux.end:
            course_data[str(c['course_id'])] = {
                'course_name': aux.display_name_with_default,
                'image': course_image_url(aux),
                'discussions': list(EolForumNotificationsDiscussions.objects.filter(course_id=c['course_id']).values(
                    'discussion_id',
                    'block_key',
                    'daily_threads',
                    'daily_comment',
                    'weekly_threads',
                    'weekly_comment'
                    ))
            }
    return course_data

def get_user_data(discussion_id, user, course_key, block_key):
    """
        return user notification data
    """
    if EolForumNotificationsDiscussions.objects.filter(discussion_id=discussion_id, course_id=course_key).exists():
        try:
            aux = EolForumNotificationsUser.objects.get(discussion__discussion_id=discussion_id, user=user, discussion__course_id=course_key)
            return json.dumps({
                'how_often': aux.how_often
            })
        except EolForumNotificationsUser.DoesNotExist:
            logger.info('EolForumNotification - Error to get notif model, discussion {}, user: {}'.format(discussion_id, user))
            return '{}'
    else:
        EolForumNotificationsDiscussions.objects.create(discussion_id=discussion_id, course_id=course_key, block_key=block_key)
        return '{}'

def get_block_info(block_key):
    """
        get displat name and parent id from block_key
    """
    store = modulestore()
    default = 'Discusión'
    try:
        with store.bulk_operations(block_key.course_key):
            block = store.get_item(block_key)
            return {
                'display_name': block.display_name or default,
                'parent': str(block.parent)
            }
    except Exception as e:
        logger.info('EolForumNotification - Error to get block data, block id: {}'.format(block_key))
        return {
                'display_name': default,
                'parent': ''
            }

def get_info_block_course(discussion_id, course_id):
    """
        get course and discussion display_name
    """
    try:
        course_key = CourseKey.from_string(course_id)
        discussion = EolForumNotificationsDiscussions.objects.get(discussion_id=discussion_id, course_id=course_key)
        block_info = get_block_info(discussion.block_key)
        course = get_course_by_id(course_key)
        return {
            'course_name': course.display_name_with_default,
            'discussion_name': block_info['display_name']
        }
    except Exception as e:
        logger.info('EolForumNotification - Error to get block and course data, course id: {}, discussion_id: {}'.format(course_id, discussion_id))
        return None
