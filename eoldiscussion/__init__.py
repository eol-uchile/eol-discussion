# -*- coding: utf-8 -*-
"""
Discussion XBlock
"""
# Python Standard Libraries
from datetime import datetime as dt
import logging
import os, re
import pkg_resources

# Installed packages (via pip)
from django.conf import settings as dsettings
from django.contrib.auth.models import User
from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import reverse
from django.utils import timezone
from eol_forum_notifications.utils import get_user_data
from mako.lookup import TemplateLookup
from six.moves import urllib

# Edx dependencies
from openedx.core.djangolib.markup import HTML, Text
from web_fragments.fragment import Fragment
from xblock_discussion import DiscussionXBlock
from xblock.core import XBlock
from xblock.exceptions import JsonHandlerError
from xblock.fields import Scope, String, Integer, Boolean
from xblockutils.resources import ResourceLoader
from openedx.core.djangoapps.django_comment_common.models import Role

log = logging.getLogger(__name__)
loader = ResourceLoader(__name__)  # pylint: disable=invalid-name


def _(text):
    """
    A noop underscore function that marks strings for extraction.
    """
    return text


@XBlock.needs('user')  # pylint: disable=abstract-method
@XBlock.needs('i18n')
class EolDiscussionXBlock(DiscussionXBlock):
    """
    Provides an extension of DiscussionXBlock adding new functionalities.
    """
    limit_character = Integer(
        display_name=_('Character limit'),
        help=_('Integer representing the character limit between 1 and 2,000.'),
        default=1000,
        values={'min': 1, 'max':2000},
        scope=Scope.settings,
    )
    is_dated = Boolean(
        display_name=_("Schedule forum"),
        default=False,
        scope=Scope.settings,
        help=_("The forum will only be visible during the configured dates.")
    )
    start_date = String(
        display_name=_("Start date"),
        scope=Scope.settings,
        help=_("Indicate the start date of the forum")
    )

    end_date = String(
        display_name=_("End date"),
        scope=Scope.settings,
        help=_("Indicate the end date of the forum")
    )

    editable_fields = ["display_name", "discussion_category", "discussion_target", "limit_character", "is_dated", "start_date", "end_date"]

    def resource_string(self, path):
        """Handy helper for getting resources from our kit."""
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")
    
    def render_mako_template(self, path, context):
        pkg_dir = os.path.dirname(__file__)
        lookup = TemplateLookup(directories=[pkg_dir], input_encoding="utf-8", output_encoding="utf-8")
        tmpl = lookup.get_template(path)
        return tmpl.render(**context).decode("utf-8")
    
    def include_mako_static(self, path, context):
        raw = self.resource_string(path)
        replace = lambda match: str(context.get(match.group(1), match.group(0)))
        return re.sub(r"\$\{([^}]+)\}", replace, raw)
    
    def is_course_staff(self):
        # pylint: disable=no-member
        """
         Check if user is course staff.
        """
        return getattr(self.xmodule_runtime, 'user_is_staff', False)

    def is_instructor(self):
        # pylint: disable=no-member
        """
        Check if user role is instructor.
        """
        return self.xmodule_runtime.get_user_role() == 'instructor'

    def has_dicussion_permission(self):
        """
            Verify if user has forum permission
        """
        user = User.objects.get(id=self.scope_ids.user_id)
        roles = Role.objects.filter(users=user, course_id=self.course_key).values('name')
        roles = [x['name'] for x in roles]
        for x in roles:
            if x in ['Moderator', 'Administrator']:
                return True
        return False

    def show_staff_grading_interface(self):
        """
        Return if current user is staff and not in studio.
        """
        in_studio_preview = self.scope_ids.user_id is None
        return (self.is_course_staff() or self.is_instructor() or self.has_dicussion_permission()) and not in_studio_preview

    def student_view(self, context=None):
        """
        Renders student view for LMS.
        """
        fragment = Fragment()
        # Head dependencies
        for vendor_js_file in self.vendor_js_dependencies():
            fragment.add_resource_url(staticfiles_storage.url(vendor_js_file), "application/javascript", "head")
        fragment.add_css(self.resource_string("static/css/inline-discussion.css"))
        fragment.add_javascript(self.resource_string("static/js/discussion.js"))

        login_msg = ''

        if not self.django_user.is_authenticated:
            qs = urllib.parse.urlencode({
                'course_id': self.course_key,
                'enrollment_action': 'enroll',
                'email_opt_in': False,
            })
            login_msg = Text(_(u"You are not signed in. To view the discussion content, {sign_in_link} or "
                               u"{register_link}, and enroll in this course.")).format(
                sign_in_link=HTML(u'<a href="{url}">{sign_in_label}</a>').format(
                    sign_in_label=_('sign in'),
                    url='{}?{}'.format(reverse('signin_user'), qs),
                ),
                register_link=HTML(u'<a href="/{url}">{register_label}</a>').format(
                    register_label=_('register'),
                    url='{}?{}'.format(reverse('register_user'), qs),
                ),
            )

        context = {
            'discussion_id': self.discussion_id,
            'display_name': self.display_name if self.display_name else _("Discussion"),
            'limit_character': self.limit_character,
            'user': self.django_user,
            'course_id': self.course_key,
            'discussion_category': self.discussion_category,
            'discussion_target': self.discussion_target,
            'can_create_thread': self.has_permission("create_thread"),
            'can_create_comment': self.has_permission("create_comment"),
            'can_create_subcomment': self.has_permission("create_sub_comment"),
            'login_msg': login_msg,
            'is_staff': self.show_staff_grading_interface(),
            'is_dated': self.is_dated,
            'start': '',
            'finish': '',
            'icon1_url': self.runtime.local_resource_url(self,"static/images/icono-01.png"),
            'icon2_url': self.runtime.local_resource_url(self,"static/images/icono-02.png"),
            'icon3_url': self.runtime.local_resource_url(self,"static/images/icono-03.png"),
            'pencil_icon_black_url': self.runtime.local_resource_url(self,"static/images/pencil_icon_black.png"),
            'started': '',
            'finished': '',
            'include_mako_static': lambda path: self.include_mako_static(path, context)
        }
        if self.is_dated:
            dt1 = dt.fromisoformat(self.start_date.replace("Z", "+00:00"))
            dt2 = dt.fromisoformat(self.end_date.replace("Z", "+00:00"))
            context['start'] = self.start_date
            context['finish'] = self.end_date
            now = timezone.now()
            context['started'] = dt1 <= now
            context['finished'] =  dt2 < now
        try:
            notification_data = get_user_data(self.discussion_id, self.django_user, self.course_key, self.location)
            context['url_eol_notification_save'] = reverse('eol_discussion_notification:save')
            context['notification_data'] = notification_data
        except ImportError:
            context['url_eol_notification_save'] = ''
            context['notification_data'] = '{}'
        fragment.add_content(self.render_mako_template('static/html/_discussion_inline.html', context))
        fragment.initialize_js('EolDiscussionInlineBlock')

        return fragment

    def studio_view(self, context):
        """
        Render a form for editing this XBlock
        """
        fragment = Fragment()
        context = {
            'fields': {},
            'xblock': self
        }
        # Build a list of all the fields that can be edited:
        for field_name in self.editable_fields:
            field = self.fields[field_name]
            assert field.scope in (Scope.content, Scope.settings), (
                "Only Scope.content or Scope.settings fields can be used with "
                "StudioEditableXBlockMixin. Other scopes are for user-specific data and are "
                "not generally created/configured by content authors in Studio."
            )
            field_info = self._make_field_info(field_name, field)
            if field_info is not None:
                context["fields"][field_name] = field_info
        fragment.content = loader.render_django_template('static/html/studio_edit.html', context)
        fragment.add_css(self.resource_string("static/css/eoldiscussion_studio.css"))
        fragment.add_javascript(loader.load_unicode('static/js/studio_edit.js'))
        settings = {
            'is_dated': self.is_dated
        }
        fragment.initialize_js('StudioEditableXBlockMixin', json_args=settings)
        return fragment


    @XBlock.json_handler
    def submit_studio_edits(self, data, suffix=''):  # pylint: disable=unused-argument
        """
        AJAX handler for studio_view() Save button
        """
        response = self.validate_data(data)
        if response is True:
            self.display_name = data.get('display_name')
            self.discussion_category = data.get('discussion_category')
            self.discussion_target = data.get('discussion_target')
            self.limit_character = data.get('limit_character')
            self.is_dated = data.get('is_dated')
            if data.get('is_dated'):
                self.start_date = data.get('start_date')
                self.end_date = data.get('end_date')
            return {'result': 'success'}
        else:
            raise JsonHandlerError(400, response)

    def validate_data(self, data):
        if is_empty(data.get('display_name', '')) or is_empty(data.get('discussion_category', '')) or is_empty(data.get('discussion_target', '')) or is_empty(data.get('limit_character', '')) or is_empty(data.get('is_dated', '')):
            log.error('EolDiscussion - Error in params {}'.format(data))
            return _('Error with parameters.')
        try:
            aux = int(data.get('limit_character'))
        except ValueError:
            log.error('EolDiscussion - Error, limit character must be integer, params: {}'.format(data))
            return _('The character limit must be an integer.')
        if data.get('is_dated', False) is True:
            if is_empty(data.get('start_date', '')) or is_empty(data.get('end_date', '')):
                log.error('EolDiscussion - Error, dates must be definied, params: {}'.format(data))
                return _('The dates for the forum have yet to be set.')
            else:
                try:
                    dt1 = dt.strptime(data.get('start_date', ''), "%Y-%m-%dT%H:%M:%S.%fZ")
                    dt2 = dt.strptime(data.get('end_date', ''), "%Y-%m-%dT%H:%M:%S.%fZ")
                    if dt2 < dt1:
                        log.error('EolDiscussion - Error, end_date must be greatest than start_date, params: {}'.format(data))
                        return _('The closing date must be later than the forum start date.')
                except Exception as e:
                    log.error('EolDiscussion - Error in date format, params: {}'.format(data))
                    return _('Error with date formats in the forum.')
        return True

def is_empty(attr):
    """
        check if attribute is empty or None
    """
    return attr == "" or attr is None
