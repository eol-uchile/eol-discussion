# Python Standard Libraries
import logging

# Installed packages (via pip)
from django.apps import apps
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from eol_forum_notifications.models import EolForumNotificationsDiscussions, EolForumNotificationsUser

# Edx dependencies
from opaque_keys.edx.django.models import CourseKey

# Internal project dependencies
from eoldiscussion.models import EolDiscussionXBlockNotification, EolDiscussionXBlockNotificationUser


logger = logging.getLogger(__name__)

def import_discussions_notification():
    """
    Import Discussion objects from eol_forum_notifications app to EolDiscussionXBlockNotification in eoldiscussion
    """
    # Obtain original data Discussion
    old_discussions = EolForumNotificationsDiscussions.objects.all()
    all_current_discussion_notification = {
        (discussion_id, str(course_id))
        for discussion_id, course_id in EolDiscussionXBlockNotification.objects.values_list(
            "discussion_id", "course_id"
        )
    }
    current_discussion_notification = 0
    new_discussion_notification = []

    # Iteration to save new discussion notification data
    for cc in old_discussions:
        if (cc.discussion_id, str(cc.course_id)) not in all_current_discussion_notification:
            discussion_notification = EolDiscussionXBlockNotification(
                discussion_id = cc.discussion_id,
                course_id = cc.course_id,
                block_key = cc.block_key,
                daily_threads = cc.daily_threads,
                daily_comment = cc.daily_comment,
                weekly_threads = cc.weekly_threads,
                weekly_comment = cc.weekly_comment
                )
            discussion_notification.full_clean()
            new_discussion_notification.append(discussion_notification)
        else:
            current_discussion_notification += 1
    try:
        EolDiscussionXBlockNotification.objects.bulk_create(new_discussion_notification, ignore_conflicts=True)
        return len(old_discussions), current_discussion_notification, len(new_discussion_notification)
    except Exception as e:
        logger.error(f'Exception happens: {e}')
        # Raise exception
        raise Exception(f"Error while copying discussions {e} from import_discussions_notification function")

def import_discussions_notification_user():
    """
    Import DiscussionUser objects from eol_forum_notifications app to EolDiscussionXBlockNotificationUser in eoldiscussion
    """
    # Obtain original data DiscussionUser
    old_notification_users = EolForumNotificationsUser.objects.all()
    all_current_user_discussion_notifications = EolDiscussionXBlockNotificationUser.objects.values_list("discussion_notification__discussion_id", "user_id")
    current_discussion_notifications = 0
    new_discussion_notifications_user  = []

    # Iterate to save new discussion notifications user
    for user_notification in old_notification_users:
        if (user_notification.discussion.discussion_id, user_notification.user.id) not in all_current_user_discussion_notifications:
            discussion_notification_user = EolDiscussionXBlockNotificationUser(
                discussion_notification = EolDiscussionXBlockNotification.objects.get(discussion_id = user_notification.discussion.discussion_id),
                user = User.objects.get(id = user_notification.user.id),
                how_often = user_notification.how_often
            )
            discussion_notification_user.full_clean()
            new_discussion_notifications_user.append(discussion_notification_user)
        else:
            current_discussion_notifications += 1
    try:
        EolDiscussionXBlockNotificationUser.objects.bulk_create(new_discussion_notifications_user, ignore_conflicts=True)
        return len(old_notification_users), current_discussion_notifications, len(new_discussion_notifications_user)
    except Exception as e:
        logger.error(f'Exception happens: {e}')
        # Raise exception
        raise Exception(f"Error while copying discussion notifications {e} from import_discussions_notification_user function") 

class Command(BaseCommand):
    help = """
        The eoldiscussion was changed from the previous models in eol_forum_notifications ( eol_forum_notifications.EolForumNotificationsDiscussions, eol_forum_notifications.EolForumNotificationsUser ) and mapped to the current models used in 
        this application ( eoldiscussion.EolDiscussionXBlockNotification, eoldiscussion.EolDiscussionXBlockNotificationUser ), with the sole purpose of migrating the historical data. This command does not introduce new functionality 
        or modify existing business logic; it is strictly limited to transferring and mapping the existing information.
        """ 
    def add_arguments(self, parser):
        parser.add_argument('--dry_run', action='store_true')

    def handle(self, *args, **options):
        # Check if eol_forum_notifications is installed
        if not(apps.is_installed('eol_forum_notifications')) or not(apps.is_installed('eoldiscussion')):
            self.stdout.write(
                self.style.ERROR(
                    f"One of the apps, eol_forum_notifications or eoldiscussion, isn't installed, so I can't continue with the commands."
                )
            )
            logger.error(f"One of the apps, eol_forum_notifications or eoldiscussion, isn't installed, so I can't continue with the commands.")
            raise

        dry_run = options['dry_run']
        with transaction.atomic():
            try:
                discussion_notification_import_result = import_discussions_notification()
                notification_user_import_result = import_discussions_notification_user()
                if  dry_run:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"""
                                This is a dry_run
                                
                                A total of {discussion_notification_import_result[0]} category objects were found.
                                A total of {discussion_notification_import_result[1]} objects already exist in CourseCategory model.
                                A total of {discussion_notification_import_result[2]} objects could be copied to the CourseCategory model.

                                A total of {notification_user_import_result[0]} old discussion objects were found.
                                A total of {notification_user_import_result[1]} objects already exist in EolDiscussionXBlockNotification model.
                                A total of {notification_user_import_result[2]} objects could be copied to the EolDiscussionXBlockNotification model.
                            """
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"""
                                A total of {discussion_notification_import_result[0]} category objects were found.
                                A total of {discussion_notification_import_result[1]} objects already exist in CourseCategory model.
                                A total of {discussion_notification_import_result[2]} objects have been copied to CourseCategory model

                                A total of {notification_user_import_result[0]} old discussion objects were found.
                                A total of {notification_user_import_result[1]} objects already exist in EolDiscussionXBlockNotification model.
                                A total of {notification_user_import_result[2]} objects have been copied to the EolDiscussionXBlockNotification model.
                            """
                        )
                    )
            except Exception as e:
                transaction.set_rollback(True)
                logger.error(f'Exception happens: {e}')
                # Raise exception
                raise Exception(f"Error while copying data: {e}")
            if  dry_run:
                transaction.set_rollback(True)
