
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from django.conf import settings

from celery import task
from django.core.mail import send_mail
from django.utils.html import strip_tags
from django.contrib.auth.models import User
from opaque_keys.edx.keys import CourseKey, UsageKey
from opaque_keys import InvalidKeyError
from django.template.loader import render_to_string
from .models import EolForumNotificationsUser, EolForumNotificationsDiscussions
from django.utils.timezone import now
from datetime import timedelta
import logging
logger = logging.getLogger(__name__)

EMAIL_DEFAULT_RETRY_DELAY = 30
EMAIL_MAX_RETRIES = 5

@task(
    queue='edx.lms.core.low',
    default_retry_delay=EMAIL_DEFAULT_RETRY_DELAY,
    max_retries=EMAIL_MAX_RETRIES)
def task_send_single_email(discussion_id, course_id, context):
    subject = 'Nueva actividad en el foro de {}'.format(context['platform_name'])
    emails = [context['email']]
    html_message = render_to_string('eol_forum_notifications/email.html', context)
    plain_message = strip_tags(html_message)
    from_email = configuration_helpers.get_value(
        'email_from_address',
        settings.BULK_EMAIL_DEFAULT_FROM_EMAIL
    )
    mail = send_mail(
        subject,
        plain_message,
        from_email,
        emails,
        fail_silently=False,
        html_message=html_message)
    return mail
