# Python Standard Libraries
import logging

# Installed packages (via pip)
from django.db import transaction
from django.dispatch import receiver

# Edx dependencies
from openedx.core.djangoapps.django_comment_common import signals

# Internal project dependencies 
from eoldiscussion.models import EolDiscussionXBlockNotification

log = logging.getLogger(__name__)

@receiver(signals.comment_created)
def eol_comment_created_notification_update(sender, user, post, **kwargs):
    with transaction.atomic():
        try:   
            discussion = EolDiscussionXBlockNotification.objects.get(discussion_id=post.thread.commentable_id, course_id=post.thread.course_id)
            discussion.daily_comment += 1
            discussion.weekly_comment += 1
            discussion.save()
        except Exception as e:
            log.info("EolForumNotifications - Error to increment comment count. discussion_id: {}, course: {}, error: {}".format(
                post.thread.commentable_id,
                post.thread.course_id,
                str(e)))

@receiver(signals.thread_created)
def eol_thread_created_notification_update(sender, user, post, **kwargs):
    with transaction.atomic():
        try:
            discussion = EolDiscussionXBlockNotification.objects.get(discussion_id=post.commentable_id, course_id=post.course_id)
            discussion.daily_threads += 1
            discussion.weekly_threads += 1
            discussion.save()
        except Exception as e:
            log.info("EolForumNotifications - Error to increment thread count. discussion_id: {}, course: {}, error: {}".format(
                post.commentable_id,
                post.course_id,
                str(e)))

