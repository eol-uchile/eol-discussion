from django.core.management.base import BaseCommand, CommandError

from opaque_keys.edx.keys import CourseKey
from django.contrib.auth.models import User
from django.conf import settings
from eol_forum_notifications.views import send_notification

import datetime
from django.utils import timezone

import logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'This command will send notification emails.'

    def add_arguments(self, parser):
        parser.add_argument(
            'how_often',
            help='period when notification will be sent',
            default=None
        )

    def handle(self, *args, **options):
        logger.info('EolForumNoticationsCommand - Running send_notification()')
        if options['how_often'] not in ['weekly', 'daily']:
            raise CommandError("EolForumNoticationsCommand - how_often must be 'weekly' or 'daily'")
        how_often = options['how_often']
        send_notification(how_often)
