# Python Standard Libraries
import logging

# Installed packages (via pip)
from django.core.management.base import BaseCommand, CommandError

# Internal project dependencies
from eoldiscussion.views import send_notification

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
