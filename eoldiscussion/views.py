#!/usr/bin/env python
# -- coding: utf-8 --
# Python Standard Libraries
from urllib.parse import urlencode
import logging
import uuid

# Installed packages (via pip)
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.db import transaction
from django.http import HttpResponse
from django.http import HttpResponseNotFound
from django.shortcuts import render
from django.urls import reverse

# Edx dependencies
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from opaque_keys.edx.keys import CourseKey

# Internal project dependencies
from eoldiscussion.models import EolDiscussionXBlockNotificationUser, EolDiscussionXBlockNotification
from eoldiscussion.tasks import task_send_single_email
from eoldiscussion.utils import get_users_notifications, get_courses_onlive, get_block_info, get_info_block_course

logger = logging.getLogger(__name__)
from_email = configuration_helpers.get_value('email_from_address', settings.DEFAULT_FROM_EMAIL)
msg_error = f"contáctese al correo {from_email} adjuntando el número del error"

def save_notification_get(request):
    """
        Save notifications page GET
    """
    id_error = str(uuid.uuid4())
    if request.method != "GET":
        logger.error('EolForumNotification - Wrong Method: {}, only GET'.format(request.method))
        return HttpResponse(status=400)
    if 'discussion_id' not in request.GET or 'course_id' not in request.GET or 'user_id' not in request.GET:
        logger.error('EolForumNotification - Missing Data: {}'.format(request.GET))
        return HttpResponseNotFound('(Error {} ) Error con los parametros, por favor {}'.format(id_error, msg_error))
    if request.user.is_anonymous:
        logger.error('EolForumNotification - User is anonymous, data: {}'.format(request.GET))
        return HttpResponseNotFound('Inicie sesión y vuelva a presionar el link.')
    if request.GET.get('user_id') != str(request.user.id):
        logger.error('EolForumNotification - User Ids are differents, user id get: {}, user id resquest: {}'.format(request.GET.get('user_id'), request.user.id))
        return HttpResponseNotFound('(Error {} ) Error con los parametros usuarios, por favor {}'.format(id_error, msg_error))

    try:
        course_id = CourseKey.from_string(request.GET.get('course_id'))
        discussion = EolDiscussionXBlockNotification.objects.get(discussion_id=request.GET.get('discussion_id'), course_id=course_id)
        user_notif = EolDiscussionXBlockNotificationUser.objects.get(
            user=request.user,
            discussion=discussion)
        context = {
            'discussion_id': request.GET.get('discussion_id'),
            'course_id':request.GET.get('course_id'),
            'user_id':request.GET.get('user_id'),
            'period': user_notif.how_often,
            'save_btn': True
        }
        data = get_info_block_course(request.GET.get('discussion_id'),request.GET.get('course_id'))
        if data:
            context.update(data)
        return render(request, 'eoldiscussion/notification.html', context)
    except Exception as e:
        logger.error('EolForumNotification - Error to get EolDiscussionXBlockNotificationUser, error {}, data: {}'.format(str(e), request.GET))
        return HttpResponseNotFound('(Error {} ) Error con el modelo, por favor {}'.format(id_error, msg_error))


def save_notification_post(request):
    """
        Save notifications page POST
    """
    id_error = str(uuid.uuid4())
    if request.method != "POST":
        logger.error('EolForumNotification - Wrong Method: {}, only POST'.format(request.method))
        return HttpResponse(status=400)
    if 'period' not in request.POST or 'discussion_id' not in request.POST or 'course_id' not in request.POST or 'user_id' not in request.POST:
        logger.error('EolForumNotification - Missing Data: {}'.format(request.POST))
        return render(request, 'eoldiscussion/notification.html', {'error': '(Error {} ) Error con los parametros, por favor {}'.format(id_error, msg_error)})
    if request.user.is_anonymous:
        logger.error('EolForumNotification - User is anonymous, data: {}'.format(request.POST))
        return render(request, 'eoldiscussion/notification.html', {'error':'Inicie sesión y vuelva a presionar el link del correo.'})
    if request.POST.get('user_id') != str(request.user.id):
        logger.error('EolForumNotification - User Ids are differents, user id post: {}, user id resquest: {}'.format(request.POST.get('user_id'), request.user.id))
        return render(request, 'eoldiscussion/notification.html', {'error':'(Error {} ) Error con los parametros usuarios, por favor {}'.format(id_error, msg_error)})
    if request.POST.get('period') not in ['never', 'daily', 'weekly']:
        logger.error('EolForumNotification - Period not in (never, weekly, daily), Data: {}'.format(request.POST))
        return render(request, 'eoldiscussion/notification.html', {'error': '(Error {} ) Error con el parametro periodo, por favor {}'.format(id_error, msg_error)})
    with transaction.atomic():
        try:
            course_id = CourseKey.from_string(request.POST.get('course_id'))
            discussion = EolDiscussionXBlockNotification.objects.get(discussion_id=request.POST.get('discussion_id'), course_id=course_id)
            EolDiscussionXBlockNotificationUser.objects.update_or_create(
                user=request.user,
                discussion=discussion,
                defaults={
                    'how_often': request.POST.get('period')
                    })
            context = {
                'discussion_id': request.POST.get('discussion_id'),
                'course_id':request.POST.get('course_id'),
                'user_id':request.POST.get('user_id'),
                'period': request.POST.get('period'),
                'save': True,
                'save_btn': True
            }
            data = get_info_block_course(request.POST.get('discussion_id'),request.POST.get('course_id'))
            if data:
                context.update(data)
            return render(request, 'eoldiscussion/notification.html', context)
        except Exception as e:
            logger.error('EolForumNotification - Error to update or create EolDiscussionXBlockNotificationUser, error {}, data: {}'.format(str(e), request.POST))
            return render(request, 'eoldiscussion/notification.html', {'error': '(Error {} ) Un error inesperado ha ocurrido, por favor {}'.format(id_error, msg_error)})

def save_notification(request):
    """
        Save notifications on forum xblock
    """
    if request.method != "POST":
        logger.error('EolForumNotification - Wrong Method: {}, only POST'.format(request.method))
        return HttpResponse(status=400)
    if 'period' not in request.POST or 'discussion_id' not in request.POST or 'course_id' not in request.POST or 'user_id' not in request.POST:
        logger.error('EolForumNotification - Missing Data: {}'.format(request.POST))
        return HttpResponse(status=400)
    if request.user.is_anonymous:
        logger.error('EolForumNotification - User is anonymous, data: {}'.format(request.POST))
        return HttpResponse(status=400)
    if request.POST.get('user_id') != str(request.user.id):
        logger.error('EolForumNotification - User Ids are differents, user id post: {}, user id resquest: {}'.format(request.POST.get('user_id'), request.user.id))
        return HttpResponse(status=400)
    if request.POST.get('period') not in ['never', 'daily', 'weekly']:
        logger.error('EolForumNotification - Period not in (never, weekly, daily), Data: {}'.format(request.POST))
        return HttpResponse(status=400)
    with transaction.atomic():
        try:
            course_id = CourseKey.from_string(request.POST.get('course_id'))
            discussion = EolDiscussionXBlockNotification.objects.get(discussion_id=request.POST.get('discussion_id'), course_id=course_id)
            EolDiscussionXBlockNotificationUser.objects.update_or_create(
                user=request.user,
                discussion=discussion,
                defaults={
                    'how_often': request.POST.get('period')
                    })
            return HttpResponse(status=200)
        except Exception as e:
            logger.error('EolForumNotification - Error to update or create EolDiscussionXBlockNotificationUser, error {}, data: {}'.format(str(e), request.POST))
            return HttpResponse(status=400)

def send_notification(how_often):
    """
        Send email with threads and/or comments unreaded
    """
    try:
        current_site = get_current_site()
        platform_name =  current_site.configuration.get_value('PLATFORM_NAME', settings.PLATFORM_NAME)
        url_site =  current_site.configuration.get_value('LMS_BASE', settings.LMS_ROOT_URL)
    except Exception:
        logger.error('EolForumNotification - Error to get platform name and url site')
        platform_name =  settings.PLATFORM_NAME
        url_site = settings.LMS_ROOT_URL
    courses_data = get_courses_onlive()
    for course in courses_data:
        for discussion in courses_data[course]['discussions']:
            users_notifications = get_users_notifications(how_often, discussion['discussion_id'], course)
            block = get_block_info(discussion['block_key'])
            if block['parent'] == "":
                logger.info('EolForumNotification - Block id doesnt exists, {}, course: {}'.format(discussion['block_key'], course))
                continue
            for user in users_notifications:
                context = {
                    'user_id':user['user__id'],
                    'email': user['user__email'],
                    'course_name': courses_data[course]['course_name'],
                    'image': courses_data[course]['image'],
                    'platform_name': platform_name,
                    'url_site': url_site,
                    'how_often': how_often,
                    'discussion_name': block['display_name'],
                    'parent': block['parent'],
                    'course_id': course,
                    'notif_url': '{}{}?{}'.format(
                        url_site,
                        reverse('eol_discussion_notification:save_get'),
                        urlencode({
                            'course_id': course,
                            'user_id':user['user__id'],
                            'discussion_id': discussion['discussion_id'],
                        })
                    )
                }
                context.update(discussion)
                context.pop('block_key')
                task_send_single_email.delay(discussion['discussion_id'], course, context)
            logger.info('EolForumNotification - emails sent, how_often: {}'.format(how_often))
            with transaction.atomic():
                discussion_model = EolDiscussionXBlockNotification.objects.get(discussion_id=discussion['discussion_id'], course_id=CourseKey.from_string(course))
                if how_often == 'daily':
                    discussion_model.daily_threads = 0
                    discussion_model.daily_comment = 0
                else:
                    discussion_model.weekly_threads = 0
                    discussion_model.weekly_comment = 0
                discussion_model.save()
                logger.info('EolForumNotification - {} threads/comment count reset, course: {}, discussion_id: {}'.format(how_often, course, discussion['discussion_id']))
    
