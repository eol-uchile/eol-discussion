# -*- coding: utf-8 -*-
"""
Discussion XBlock
"""
# Python Standard Libraries
from datetime import datetime as dt
import logging

# Installed packages (via pip)
from django.conf import settings as dsettings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import reverse
from django.utils.translation import get_language_bidi
from eol_forum_notifications.utils import get_user_data
from six.moves import urllib
import pkg_resources
import six

# Edx dependencies
from openedx.core.djangolib.markup import HTML, Text
from openedx.core.lib.xblock_builtin import get_css_dependencies, get_js_dependencies
from web_fragments.fragment import Fragment
from xblock.core import XBlock
from xblock.exceptions import JsonHandlerError
from xblock.fields import Scope, String, UNIQUE_ID, Integer, Boolean
from xblockutils.resources import ResourceLoader
from xblockutils.studio_editable import StudioEditableXBlockMixin
from xmodule.raw_module import RawDescriptor
from xmodule.xml_module import XmlParserMixin

log = logging.getLogger(__name__)
loader = ResourceLoader(__name__)  # pylint: disable=invalid-name


def _(text):
    """
    A noop underscore function that marks strings for extraction.
    """
    return text


@XBlock.needs('user')  # pylint: disable=abstract-method
@XBlock.needs('i18n')
class EolDiscussionXBlock(XBlock, StudioEditableXBlockMixin, XmlParserMixin):
    """
    Provides a discussion forum that is inline with other content in the courseware.
    """
    #completion_mode = XBlockCompletionMode.EXCLUDED

    discussion_id = String(scope=Scope.settings, default=UNIQUE_ID)
    display_name = String(
        display_name=_("Display Name"),
        help=_("Nombre para mostrar en este componente."),
        default="Nuevo foro de discusión",
        scope=Scope.settings
    )
    discussion_category = String(
        display_name=_("Category"),
        default=_("Week 1"),
        help=_(
            "Nombre de categoría para la discusión. "
            "Este aparece en el panel izquierdo de la discusión del curso."
        ),
        scope=Scope.settings
    )
    discussion_target = String(
        display_name=_("Subcategory"),
        default="Topic-Level Student-Visible Label",
        help=_("Nombre de subcategoría para la discusión. Este aparece en el panel izquierdo de la pantalla de foros de discusión del curso."),
        scope=Scope.settings
    )
    limit_character = Integer(
        display_name='Límite de caracteres',
        help='Entero que representa el límite de caracteres entre 1 y 2.000.',
        default=1000,
        values={'min': 1, 'max':2000},
        scope=Scope.settings,
    )
    is_dated = Boolean(
        display_name=_("Programar foro"),
        default=False,
        scope=Scope.settings,
        help=_("El foro será visible solamente durante las fechas configuradas.")
    )
    start_date = String(
        display_name=_("Fecha de inicio"),
        scope=Scope.settings,
        help=_("Indica la fecha de inicio del foro (horario chileno)")
    )

    end_date = String(
        display_name=_("Fecha de cierre"),
        scope=Scope.settings,
        help=_("Indica la fecha de cierre del foro (horario chileno)")
    )

    sort_key = String(scope=Scope.settings)

    editable_fields = ["display_name", "discussion_category", "discussion_target", "limit_character", "is_dated", "start_date", "end_date"]

    has_author_view = True  # Tells Studio to use author_view

    # support for legacy OLX format - consumed by XmlParserMixin.load_metadata
    metadata_translations = dict(RawDescriptor.metadata_translations)
    metadata_translations['id'] = 'discussion_id'
    metadata_translations['for'] = 'discussion_target'

    @property
    def course_key(self):
        """
        :return: int course id

        NB: The goal is to move this XBlock out of edx-platform, and so we use
        scope_ids.usage_id instead of runtime.course_id so that the code will
        continue to work with workbench-based testing.
        """
        return getattr(self.scope_ids.usage_id, 'course_key', None)

    @property
    def django_user(self):
        """
        Returns django user associated with user currently interacting
        with the XBlock.
        """
        user_service = self.runtime.service(self, 'user')
        if not user_service:
            return None
        return user_service._django_user  # pylint: disable=protected-access

    @staticmethod
    def vendor_js_dependencies():
        """
        Returns list of vendor JS files that this XBlock depends on.

        The helper function that it uses to obtain the list of vendor JS files
        works in conjunction with the Django pipeline to ensure that in development mode
        the files are loaded individually, but in production just the single bundle is loaded.
        """
        return get_js_dependencies('discussion_vendor')

    @staticmethod
    def js_dependencies():
        """
        Returns list of JS files that this XBlock depends on.

        The helper function that it uses to obtain the list of JS files
        works in conjunction with the Django pipeline to ensure that in development mode
        the files are loaded individually, but in production just the single bundle is loaded.
        """
        return get_js_dependencies('discussion')

    @staticmethod
    def css_dependencies():
        """
        Returns list of CSS files that this XBlock depends on.

        The helper function that it uses to obtain the list of CSS files
        works in conjunction with the Django pipeline to ensure that in development mode
        the files are loaded individually, but in production just the single bundle is loaded.
        """
        if get_language_bidi():
            return get_css_dependencies('style-inline-discussion-rtl')
        else:
            return get_css_dependencies('style-inline-discussion')

    def add_resource_urls(self, fragment):
        """
        Adds URLs for JS and CSS resources that this XBlock depends on to `fragment`.
        """
        # Head dependencies
        for vendor_js_file in self.vendor_js_dependencies():
            fragment.add_resource_url(staticfiles_storage.url(vendor_js_file), "application/javascript", "head")


    def has_permission(self, permission):
        """
        Encapsulates lms specific functionality, as `has_permission` is not
        importable outside of lms context, namely in tests.

        :param user:
        :param str permission: Permission
        :rtype: bool
        """
        # normal import causes the xmodule_assets command to fail due to circular import - hence importing locally
        from lms.djangoapps.discussion.django_comment_client.permissions import has_permission

        return has_permission(self.django_user, permission, self.course_key)

    def resource_string(self, path):
        """Handy helper for getting resources from our kit."""
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")

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
        from openedx.core.djangoapps.django_comment_common.models import Role
        from django.contrib.auth.models import User
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
            'started': '',
            'finished': ''
        }
        if self.is_dated:
            from django.utils import timezone
            #edit the code below according to your time zone
            zone = '-04:00'
            if dsettings.USER_API_DEFAULT_PREFERENCES.get('time_zone', 'America/Santiago') == 'America/Santiago':
                zone = '-03:00'
            dt1 = dt.fromisoformat('{}{}'.format(self.start_date, zone))
            dt2 = dt.fromisoformat('{}{}'.format(self.end_date, zone))
            context['start'] = '{}{}'.format(self.start_date, zone)
            context['finish'] = '{}{}'.format(self.end_date, zone)
            now = timezone.now()
            if dt1 > now:
                context['started'] = False
            else:
                context['started'] = True
            if dt2 < now:
                context['finished'] = True
            else:
                context['finished'] = False
        try:

            notification_data = get_user_data(self.discussion_id, self.django_user, self.course_key, self.location)
            context['url_eol_notification_save'] = reverse('eol_discussion_notification:save')
            context['notification_data'] = notification_data
        except ImportError:
            context['url_eol_notification_save'] = ''
            context['notification_data'] = '{}'
        fragment.add_content(self.runtime.render_template('eoldiscussion/_discussion_inline.html', context))
        fragment.initialize_js('EolDiscussionInlineBlock')

        return fragment

    def author_view(self, context=None):  # pylint: disable=unused-argument
        """
        Renders author view for Studio.
        """
        fragment = Fragment()
        fragment.add_content(self.runtime.render_template(
            'discussion/_discussion_inline_studio.html',
            {'discussion_id': self.discussion_id}
        ))
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
            return 'Error con los parámetros.'
        try:
            aux = int(data.get('limit_character'))
        except ValueError:
            log.error('EolDiscussion - Error, limit character must be integer, params: {}'.format(data))
            return 'El limite de caracteres debe ser un entero.'
        if data.get('is_dated', False) is True:
            if is_empty(data.get('start_date', '')) or is_empty(data.get('end_date', '')):
                log.error('EolDiscussion - Error, dates must be definied, params: {}'.format(data))
                return 'Falta definir las fechas del foro.'
            else:
                try:
                    dt1 = dt.strptime(data.get('start_date', ''), "%Y-%m-%dT%H:%M")
                    dt2 = dt.strptime(data.get('end_date', ''), "%Y-%m-%dT%H:%M")
                    if dt2 < dt1:
                        log.error('EolDiscussion - Error, end_date must be greatest than start_date, params: {}'.format(data))
                        return 'La fecha de cierre debe ser mayor a la fecha de inicio del foro.'
                except Exception as e:
                    log.error('EolDiscussion - Error in date format, params: {}'.format(data))
                    return 'Error con los formatos en las fechas del foro.'
        return True

    def student_view_data(self):
        """
        Returns a JSON representation of the student_view of this XBlock.
        """
        return {'topic_id': self.discussion_id}

    @classmethod
    def parse_xml(cls, node, runtime, keys, id_generator):
        """
        Parses OLX into XBlock.

        This method is overridden here to allow parsing legacy OLX, coming from discussion XModule.
        XBlock stores all the associated data, fields and children in a XML element inlined into vertical XML file
        XModule stored only minimal data on the element included into vertical XML and used a dedicated "discussion"
        folder in OLX to store fields and children. Also, some info was put into "policy.json" file.

        If no external data sources are found (file in "discussion" folder), it is exactly equivalent to base method
        XBlock.parse_xml. Otherwise this method parses file in "discussion" folder (known as definition_xml), applies
        policy.json and updates fields accordingly.
        """
        block = super(EolDiscussionXBlock, cls).parse_xml(node, runtime, keys, id_generator)

        cls._apply_translations_to_node_attributes(block, node)
        cls._apply_metadata_and_policy(block, node, runtime)

        return block

    @classmethod
    def _apply_translations_to_node_attributes(cls, block, node):
        """
        Applies metadata translations for attributes stored on an inlined XML element.
        """
        for old_attr, target_attr in six.iteritems(cls.metadata_translations):
            if old_attr in node.attrib and hasattr(block, target_attr):
                setattr(block, target_attr, node.attrib[old_attr])

    @classmethod
    def _apply_metadata_and_policy(cls, block, node, runtime):
        """
        Attempt to load definition XML from "discussion" folder in OLX, than parse it and update block fields
        """
        if node.get('url_name') is None:
            return  # Newer/XBlock XML format - no need to load an additional file.
        try:
            definition_xml, _ = cls.load_definition_xml(node, runtime, block.scope_ids.def_id)
        except Exception as err:  # pylint: disable=broad-except
            log.info(
                u"Exception %s when trying to load definition xml for block %s - assuming XBlock export format",
                err,
                block
            )
            return

        metadata = cls.load_metadata(definition_xml)
        cls.apply_policy(metadata, runtime.get_policy(block.scope_ids.usage_id))

        for field_name, value in six.iteritems(metadata):
            if field_name in block.fields:
                setattr(block, field_name, value)

def is_empty(attr):
    """
        check if attribute is empty or None
    """
    return attr == "" or attr is None
