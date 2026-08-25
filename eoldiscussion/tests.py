""" Tests for EolDiscussionXBlock"""
# Python Standard Libraries
from collections import namedtuple
import itertools
import json
import random
import string

# Installed packages (via pip)
from django.test import override_settings
from mock import patch, Mock
from safe_lxml import etree
from six.moves import range
import ddt
import mock

# Edx dependencies
from common.djangoapps.student.roles import CourseStaffRole
from common.djangoapps.student.tests.factories import UserFactory, CourseEnrollmentFactory
from common.djangoapps.util.testing import UrlResetMixin
from opaque_keys.edx.locator import CourseLocator
from xblock.field_data import DictFieldData
from xblock.fields import NO_CACHE_VALUE, UNIQUE_ID, ScopeIds
from xblock.runtime import Runtime
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

# Internal project dependencies
from eoldiscussion import EolDiscussionXBlock

class TestRequest(object):
    # pylint: disable=too-few-public-methods
    """
    Module helper for @json_handler
    """
    method = None
    body = None
    success = None

def attribute_pair_repr(self):
    """
    Custom string representation for the AttributePair namedtuple which is
    consistent between test runs.
    """
    return u'<AttributePair name={}>'.format(self.name)


AttributePair = namedtuple("AttributePair", ["name", "value"])
AttributePair.__repr__ = attribute_pair_repr


ID_ATTR_NAMES = ("discussion_id", "id",)
CATEGORY_ATTR_NAMES = ("discussion_category",)
TARGET_ATTR_NAMES = ("discussion_target", "for", )


def _random_string():
    """
    Generates random string
    """
    return ''.join(random.choice(string.ascii_lowercase, ) for _ in range(12))


def _make_attribute_test_cases():
    """
    Builds test cases for attribute-dependent tests
    """
    attribute_names = itertools.product(ID_ATTR_NAMES, CATEGORY_ATTR_NAMES, TARGET_ATTR_NAMES)
    for id_attr, category_attr, target_attr in attribute_names:
        yield (
            AttributePair(id_attr, _random_string()),
            AttributePair(category_attr, _random_string()),
            AttributePair(target_attr, _random_string())
        )


@ddt.ddt
class EolDiscussionXBlockImportExportTests(UrlResetMixin, ModuleStoreTestCase):
    def make_an_xblock(cls, **kw):
        """
        Helper method that creates a EolListGrade XBlock
        """
        course = cls.course
        runtime = Mock(
            course_id=course.id,
            user_is_staff=False,
            service=Mock(
                return_value=Mock(_catalog={}),
            ),
            render_template=Mock(return_value="<div class='studio-view'>Contenido Studio</div>"),
        )
        scope_ids = Mock()
        field_data = DictFieldData(kw)
        xblock = EolDiscussionXBlock(runtime, field_data, scope_ids)
        xblock.xmodule_runtime = runtime
        xblock.location = course.location
        xblock.course_id = course.id
        xblock.category = 'eollistgrade'
        return xblock
    """
    Import and export tests
    """
    def setUp(self):
        """
        Set up method
        """
        super(EolDiscussionXBlockImportExportTests, self).setUp()
        self.keys = ScopeIds("any_user", "discussion", "def_id", "usage_id")
        self.runtime_mock = mock.Mock(spec=Runtime)
        self.runtime_mock.construct_xblock_from_class = mock.Mock(side_effect=self._construct_xblock_mock)
        self.runtime_mock.get_policy = mock.Mock(return_value={})
        self.id_gen_mock = mock.Mock()
        self.course = CourseFactory.create(org='foo', course='baz', run='bar')

        self.xblock =  self.make_an_xblock()
        with patch('common.djangoapps.student.models.cc.User.save'):
            # Create staff user
            self.user = UserFactory(
                username='user',
                password='test',
                email='staff@edx.org')
            CourseEnrollmentFactory(
                user=self.user,
                course_id=self.course.id)
            CourseStaffRole(self.course.id).add_users(self.user)

    def _construct_xblock_mock(self, cls, keys):  # pylint: disable=unused-argument
        """
        Builds target xblock instance (EolDiscussionXBlock)

        Signature-compatible with runtime.construct_xblock_from_class - can be used as a mock side-effect
        """
        return EolDiscussionXBlock(self.runtime_mock, scope_ids=keys, field_data=DictFieldData({}))

    @patch("eoldiscussion.EolDiscussionXBlock.load_definition_xml")
    @ddt.unpack
    @ddt.data(*list(_make_attribute_test_cases()))
    def test_xblock_export_format(self, id_pair, category_pair, target_pair, patched_load_definition_xml):
        """
        Test that xblock export XML format can be parsed preserving field values
        """
        xblock_xml = u"""
        <discussion
            url_name="82bb87a2d22240b1adac2dfcc1e7e5e4" xblock-family="xblock.v1"
            {id_attr}="{id_value}"
            {category_attr}="{category_value}"
            {target_attr}="{target_value}"
        />
        """.format(
            id_attr=id_pair.name, id_value=id_pair.value,
            category_attr=category_pair.name, category_value=category_pair.value,
            target_attr=target_pair.name, target_value=target_pair.value,
        )
        node = etree.fromstring(xblock_xml)

        patched_load_definition_xml.side_effect = Exception("Irrelevant")

        block = self.xblock.parse_xml(node, self.runtime_mock, self.keys, self.id_gen_mock)

        self.assertEqual(block.discussion_id, id_pair.value)
        self.assertEqual(block.discussion_category, category_pair.value)
        self.assertEqual(block.discussion_target, target_pair.value)


    @patch("eoldiscussion.EolDiscussionXBlock.load_definition_xml")
    @ddt.unpack
    @ddt.data(*(_make_attribute_test_cases()))
    def test_legacy_export_format(self, id_pair, category_pair, target_pair, patched_load_definition_xml):
        """
        Test that legacy export XML format can be parsed preserving field values
        """
        xblock_xml = """<discussion url_name="82bb87a2d22240b1adac2dfcc1e7e5e4"/>"""
        xblock_definition_xml = u"""
        <discussion
            {id_attr}="{id_value}"
            {category_attr}="{category_value}"
            {target_attr}="{target_value}"
        />""".format(
            id_attr=id_pair.name, id_value=id_pair.value,
            category_attr=category_pair.name, category_value=category_pair.value,
            target_attr=target_pair.name, target_value=target_pair.value,
        )
        node = etree.fromstring(xblock_xml)
        definition_node = etree.fromstring(xblock_definition_xml)

        patched_load_definition_xml.return_value = (definition_node, "irrelevant")
        block = self.xblock.parse_xml(node, self.runtime_mock, self.keys, self.id_gen_mock)

        self.assertEqual(block.discussion_id, id_pair.value)
        self.assertEqual(block.discussion_category, category_pair.value)
        self.assertEqual(block.discussion_target, target_pair.value)

    def test_export_default_discussion_id(self):
        """
        Test that default discussion_id values are not exported.

        Historically, the OLX format allowed omitting discussion ID values; in such case, the IDs are generated
        deterministically based on the course ID and the usage ID. Moreover, Studio does not allow course authors
        to edit discussion_id, so all courses authored in Studio have discussion_id omitted in OLX.

        Forcing Studio to always export discussion_id can cause data loss when switching between an older and newer
        export,  in a course with a course ID different from the one from which the export was created - because the
        discussion ID would be different.
        """
        target_node = etree.Element('dummy')

        block = EolDiscussionXBlock(self.runtime_mock, scope_ids=self.keys, field_data=DictFieldData({}))
        discussion_id_field = block.fields['discussion_id']

        # precondition checks - discussion_id does not have a value and uses UNIQUE_ID
        self.assertEqual(
            discussion_id_field._get_cached_value(block), # pylint: disable=protected-access
            NO_CACHE_VALUE
        )
        self.assertEqual(discussion_id_field.default, UNIQUE_ID)

        block.add_xml_to_node(target_node)
        self.assertEqual(target_node.tag, "discussion")
        self.assertNotIn("discussion_id", target_node.attrib)

    @ddt.data("jediwannabe", "iddqd", "itisagooddaytodie")
    def test_export_custom_discussion_id(self, discussion_id):
        """
        Test that custom discussion_id values are exported
        """
        target_node = etree.Element('dummy')

        block = EolDiscussionXBlock(self.runtime_mock, scope_ids=self.keys, field_data=DictFieldData({}))
        
        block.discussion_id = discussion_id

        # precondition check
        self.assertEqual(block.discussion_id, discussion_id)

        block.add_xml_to_node(target_node)
        self.assertEqual(target_node.tag, "discussion")
        self.assertTrue(target_node.attrib["discussion_id"], discussion_id)

    def test_submit_studio_edits_fails_when_parameters_missing(self):
        """
            Verifies that the "Submit Studio Edits" method returns an appropriate error when not all required parameters are provided.
        """
        request = TestRequest()
        request.method = 'POST'
        data = json.dumps({
            'display_name':'',
            'discussion_category':'',
            'discussion_target':'',
            'limit_character':'',
            'is_dated':''
        })

        request.body = data.encode()
        response = self.xblock.submit_studio_edits(request)
        data = json.loads(response._app_iter[0].decode())
        self.assertEqual(data['error'], 'Error with parameters.')

    def test_submit_studio_edits_limit_character_is_not_a_number(self):
        """
            Verifies that the "Submit Studio Edits" method returns a validation error when the limit_character field is provided with a non-numeric value.
        """
        request = TestRequest()
        request.method = 'POST'
        data = json.dumps({
            'display_name':'test_name',
            'discussion_category':'test_category',
            'discussion_target':'test_target',
            'limit_character':'aaaaa',
            'is_dated': True
        })

        request.body = data.encode()
        response = self.xblock.submit_studio_edits(request)
        data = json.loads(response._app_iter[0].decode())
        self.assertEqual(data['error'], 'The character limit must be an integer.')

    def test_submit_studio_edits_handles_is_dated_false(self):
        """
            Verifies that the "Submit Studio Edits" endpoint correctly handles the is_dated boolean field when it is set to False.
        """
        request = TestRequest()
        request.method = 'POST'
        data = json.dumps({
            'display_name':'test_name',
            'discussion_category': 'test_category',
            'discussion_target': 'test_target',
            'limit_character': 1200,
            'is_dated': False
        })

        request.body = data.encode()
        response = self.xblock.submit_studio_edits(request)
        data = json.loads(response._app_iter[0].decode())
        self.assertEqual(data['result'], 'success')

    def test_submit_studio_edits_is_dated_true_requires_dates(self):
        """
            Verifies that the "Submit Studio Edits" endpoint enforces the presence of both start_date and end_date when the is_dated field is set to True.
            If either date is missing, the endpoint should return a validation error.
        """
        request = TestRequest()
        request.method = 'POST'
        data = json.dumps({
            'display_name':'test_name',
            'discussion_category': 'test_category',
            'discussion_target': 'test_target',
            'limit_character': 1200,
            'is_dated': True
        })

        request.body = data.encode()
        response = self.xblock.submit_studio_edits(request)
        data = json.loads(response._app_iter[0].decode())
        self.assertEqual(data['error'], 'The dates for the forum have yet to be set.')

    def test_submit_studio_edits_invalid_date_format(self):
        """
            Verifies that the "Submit Studio Edits" endpoint correctly handles and rejects inputs with an invalid date format
        """
        request = TestRequest()
        request.method = 'POST'
        data = json.dumps({
            'display_name':'test_name',
            'discussion_category': 'test_category',
            'discussion_target': 'test_target',
            'limit_character': 1200,
            'is_dated': True,
            'start_date':'2020-01-02',
            'end_date':'2020-01-02',
        })

        request.body = data.encode()
        response = self.xblock.submit_studio_edits(request)
        data = json.loads(response._app_iter[0].decode())
        self.assertEqual(data['error'], 'Error with date formats in the forum.')

    def test_submit_studio_edits_end_date_must_be_greater_than_start_date(self):
        """
            Verifies that the "Submit Studio Edits" endpoint returns a validation error when end_date is earlier than or equal to 'start_date'.
            The end_date must be greater than start_date.
        """
        request = TestRequest()
        request.method = 'POST'
        data = json.dumps({
            'display_name':'test_name',
            'discussion_category': 'test_category',
            'discussion_target': 'test_target',
            'limit_character': 1200,
            'is_dated': True,
            'start_date':'2025-04-28T14:30:00.000Z',
            'end_date':'2025-03-28T14:30:00.000Z',
        })

        request.body = data.encode()
        response = self.xblock.submit_studio_edits(request)
        data = json.loads(response._app_iter[0].decode())
        self.assertEqual(data['error'], 'The closing date must be later than the forum start date.')

    def test_submit_studio_edits(self):
        """
            Verify submit studio edits is working properly
        """
        request = TestRequest()
        request.method = 'POST'
        data = json.dumps({
            'display_name':'test_name',
            'discussion_category': 'test_category',
            'discussion_target': 'test_target',
            'limit_character': 1200,
            'is_dated': True,
            'start_date':'2025-03-28T14:30:00.000Z',
            'end_date':'2025-04-28T14:30:00.000Z',
        })
        request.body = data.encode()
        response = self.xblock.submit_studio_edits(request)
        data = json.loads(response._app_iter[0].decode())
        self.assertEqual(data['result'], 'success')

    def test_student_view_data(self):
        """
        Test the student_view_data() method.
        """
        response = self.xblock.student_view_data()
        self.assertEqual(response['topic_id'], self.xblock.discussion_id)

    def test_studio_view_render(self,):
        """
            Check if xblock studio template loaded correctly
        """
        studio_view = self.xblock.studio_view(None)
        studio_view_html = studio_view.content
        self.assertIn('id="settings-tab"', studio_view_html)

    def test_course_key_property(self):
        """
            Test course_key property
        """
        mock_usage_id = Mock()
        mock_usage_id.course_key = self.course.id
        mock_scope_ids = Mock()
        mock_scope_ids.usage_id = mock_usage_id
        self.xblock.scope_ids = mock_scope_ids
        response = self.xblock.course_key
        self.assertEqual(response, self.course.id)

    def test_author_view_render(self):
        """
            Check if author view is rendering
        """
        author_view = self.xblock.author_view()
        author_view_html = author_view.content
        self.assertIn('Contenido Studio', author_view_html)

    @override_settings(USER_API_DEFAULT_PREFERENCES={'time_zone':'America/Santiago'})
    @patch('lms.djangoapps.discussion.django_comment_client.permissions.has_permission', return_value=True)
    def test_student_view_render(self,_):
        """
            Check if student view is rendering
        """
        self.xblock.is_manual = True
        self.xblock.xmodule_runtime.user_is_staff = True
        self.xblock.scope_ids.user_id = self.user.id
        self.xblock.scope_ids = mock.Mock()
        self.xblock.scope_ids.usage_id = mock.Mock()
        self.xblock.scope_ids.usage_id.course_key = self.course.id
        self.xblock.is_dated = True
        self.xblock.start_date = '2024-12-01T08:00:00.000Z'
        self.xblock.end_date = '2024-12-01T17:00:00.000Z'
        student_view = self.xblock.student_view()
        student_view_html = student_view.content
        self.assertIn('discussion-module eoldiscussion-module', student_view_html)

    def test_has_dicussion_permission(self):
        """
            Check if has_dicussion_permission work properly
        """
        mock_usage_id = Mock()
        mock_usage_id.course_key = CourseLocator.from_string(str(self.course.id))
        mock_scope_ids = Mock()
        mock_scope_ids.usage_id = mock_usage_id
        self.xblock.scope_ids = mock_scope_ids
        self.xblock.scope_ids.user_id = self.user.id
        result = self.xblock.has_dicussion_permission()
        self.assertFalse(result)

# -*- coding: utf-8 -*-
# Python Standard Libraries
from collections import namedtuple
from io import StringIO
import json

# Installed packages (via pip)
from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command
from django.core.management.base import CommandError
from django.http import HttpRequest, HttpResponse
from django.test import Client, TestCase
from django.test.utils import override_settings
from django.urls import reverse
from mock import patch, MagicMock

# Edx dependencies
from common.djangoapps.student.roles import CourseStaffRole
from common.djangoapps.student.tests.factories import UserFactory, CourseEnrollmentFactory
from common.djangoapps.util.testing import UrlResetMixin
from opaque_keys.edx.keys import UsageKey
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

# Internal project dependencies
from .models import EolForumNotificationsUser, EolForumNotificationsDiscussions
from .utils import get_user_data, get_info_block_course, get_block_info
from .views import send_notification, save_notification, save_notification_get, save_notification_post

class TestRequest(object):
    # pylint: disable=too-few-public-methods
    """
    Module helper for @json_handler
    """
    method = None
    body = None
    success = None
    params = None
    headers = None

class TestNotifiactionsDiscussion(UrlResetMixin, ModuleStoreTestCase):

    def setUp(self):
        super(TestNotifiactionsDiscussion, self).setUp()
        self.course = CourseFactory.create(org='foo', course='baz', run='bar')
        self.block_key = UsageKey.from_string('block-v1:eol+test100+2021_1+type@eoldiscussion+block@5c13942678184cab9a5345b660292c6e')
        self.discussion = EolForumNotificationsDiscussions.objects.create(
            discussion_id= "1234567890",
            course_id= self.course.id,
            block_key=self.block_key
            )
        with patch('common.djangoapps.student.models.cc.User.save'):
            # Create the student
            self.student = UserFactory(
                username='student',
                password='test',
                email='student@edx.org')
            # Enroll the student in the course
            CourseEnrollmentFactory(
                user=self.student, course_id=self.course.id)
            self.client = Client()
            self.client.login(username='student', password='test')
            self.student2 = UserFactory(
                username='student2',
                password='test',
                email='student2@edx.org')
            # Enroll the student in the course
            CourseEnrollmentFactory(
                user=self.student2, course_id=self.course.id)
            self.client2 = Client()
            self.client2.login(username='student2', password='test')
            # Create staff user
            self.staff_user = UserFactory(
                username='staff_user',
                password='test',
                email='staff@edx.org')
            CourseEnrollmentFactory(
                user=self.staff_user,
                course_id=self.course.id)
            CourseStaffRole(self.course.id).add_users(self.staff_user)

    def test_EolForumNotificationsDiscussions_str_function(self):
        """
            Tests that the __str__ method returns the expected format:
            '<discussion_id> - <forum_path>'.
        """
        self.assertEqual(self.discussion.__str__(),'1234567890 - foo/baz/bar')

    def test_save_notifications(self):
        """
            save_notifications() normal process
        """
        post_data = {
            'period': "daily",
            'discussion_id': self.discussion.discussion_id,
            'course_id': str(self.course.id),
            'user_id': str(self.student.id)
        }
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = self.client.post(
            reverse('eol_discussion_notification:save'), post_data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        notif = EolForumNotificationsUser.objects.get(user=self.student, discussion=self.discussion)
        self.assertEqual(notif.how_often, post_data['period'])

    def test_save_notifications_anonymous(self):
        """
            save_notifications() when user is anonymous
        """
        post_data = {
            'period': "daily",
            'discussion_id': self.discussion.discussion_id,
            'course_id': str(self.course.id),
            'user_id': str(self.student.id)
        }
        client_anonymous = Client()
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = client_anonymous.post(
            reverse('eol_discussion_notification:save'), post_data)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())

    def test_save_notifications_user_anonymous(self):
        """
        Tests save_notifications() when called by an anonymous user. 
        The view is protected with @login_required, so the function is invoked directly 
        without using reverse or making an HTTP request.
        """
        post_data = {
            'period': "daily",
            'discussion_id': self.discussion.discussion_id,
            'course_id': str(self.course.id),
            'user_id': str(self.student.id)
        }
        request = TestRequest()
        request.method = 'POST'
        request.POST =  post_data
        request.user = AnonymousUser()
        response = save_notification(request)
        self.assertEqual(response.status_code, 400)

    def test_save_notifications_wrong_method(self):
        """
            save_notifications() when request method is not post
        """
        post_data = {
            'period': "daily",
            'discussion_id': self.discussion.discussion_id,
            'course_id': str(self.course.id),
            'user_id': str(self.student.id)
        }
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = self.client.get(
            reverse('eol_discussion_notification:save'), post_data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())

    def test_save_notifications_wrong_params(self):
        """
            save_notifications() when missing a params request
        """
        post_data = {
            'discussion_id': 'ecedb9f8c633496d3fc4bd014ee30a65c75796f2',
            'course_id': str(self.course.id),
            'user_id': str(self.student.id)
        }
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = self.client.post(
            reverse('eol_discussion_notification:save'), post_data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())

    def test_save_notifications_wrong_user(self):
        """
            save_notifications() when request user is different post user
        """
        post_data = {
            'period': "daily",
            'discussion_id': self.discussion.discussion_id,
            'course_id': str(self.course.id),
            'user_id': '123'
        }
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = self.client.post(
            reverse('eol_discussion_notification:save'), post_data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())

    def test_save_notifications_wrong_course(self):
        """
            save_notifications() when course id is wrong
        """
        post_data = {
            'period': "daily",
            'discussion_id': self.discussion.discussion_id,
            'course_id': 'asdasdsadas',
            'user_id': str(self.student.id)
        }
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = self.client.post(
            reverse('eol_discussion_notification:save'), post_data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())

    def test_save_notifications_wrong_period(self):
        """
            save_notifications() when period is wrong
        """
        post_data = {
            'period': "monthly",
            'discussion_id': self.discussion.discussion_id,
            'course_id': str(self.course.id),
            'user_id': str(self.student.id)
        }
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = self.client.post(
            reverse('eol_discussion_notification:save'), post_data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())

    def test_save_notifications_wrong_no_discussion(self):
        """
            save_notifications() when discussion id is wrong
        """
        post_data = {
            'period': "daily",
            'discussion_id': '321654987',
            'course_id': str(self.course.id),
            'user_id': str(self.student.id)
        }
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=post_data['discussion_id']).exists())
        response = self.client.post(
            reverse('eol_discussion_notification:save'), post_data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=post_data['discussion_id']).exists())

    @override_settings(PLATFORM_NAME='Test')
    @override_settings(LMS_ROOT_URL='https://test.ts')
    @patch('eol_forum_notifications.views.get_block_info')
    @patch('eol_forum_notifications.utils.course_image_url')
    @patch('eol_forum_notifications.utils.get_course_by_id')
    def test_send_notifications_daily(self, course_mock, image_mock, block_mock):
        """
            test send_notifications() daily period
        """
        course_mock.side_effect = [namedtuple("Course", ["display_name_with_default", "end"])("this is a display name", None)]
        image_mock.return_value = '/assets/image.jpg'
        block_mock.return_value = {'display_name':'Test discussion xblock', 'parent': 'asdadssa'}
        user_notif = EolForumNotificationsUser.objects.create(discussion=self.discussion, user=self.student, how_often="daily")
        self.discussion.daily_threads = 3
        self.discussion.daily_comment = 3
        self.discussion.weekly_threads = 3
        self.discussion.weekly_comment = 3
        self.discussion.save()
        self.assertEqual(self.discussion.daily_threads, 3)
        self.assertEqual(self.discussion.daily_comment, 3)
        self.assertEqual(self.discussion.weekly_threads, 3)
        self.assertEqual(self.discussion.weekly_comment, 3)
        send_notification('daily')
        aux = EolForumNotificationsDiscussions.objects.get(id=self.discussion.id)
        self.assertEqual(aux.daily_threads, 0)
        self.assertEqual(aux.daily_comment, 0)
        self.assertEqual(aux.weekly_threads, 3)
        self.assertEqual(aux.weekly_comment, 3)

    @override_settings(PLATFORM_NAME='Test')
    @override_settings(LMS_ROOT_URL='https://test.ts')
    @patch('eol_forum_notifications.views.get_block_info')
    @patch('eol_forum_notifications.utils.course_image_url')
    @patch('eol_forum_notifications.utils.get_course_by_id')
    def test_send_notifications_weekly(self, course_mock, image_mock, block_mock):
        """
            test send_notifications() weekly period
        """
        course_mock.side_effect = [namedtuple("Course", ["display_name_with_default", "end"])("this is a display name", None)]
        image_mock.return_value = '/assets/image.jpg'
        block_mock.return_value = {'display_name':'Test discussion xblock', 'parent': 'asdadssa'}
        user_notif = EolForumNotificationsUser.objects.create(discussion=self.discussion, user=self.student, how_often="daily")
        self.discussion.daily_threads = 3
        self.discussion.daily_comment = 3
        self.discussion.weekly_threads = 3
        self.discussion.weekly_comment = 3
        self.discussion.save()
        self.assertEqual(self.discussion.daily_threads, 3)
        self.assertEqual(self.discussion.daily_comment, 3)
        self.assertEqual(self.discussion.weekly_threads, 3)
        self.assertEqual(self.discussion.weekly_comment, 3)
        send_notification('weekly')
        aux = EolForumNotificationsDiscussions.objects.get(id=self.discussion.id)
        self.assertEqual(aux.daily_threads, 3)
        self.assertEqual(aux.daily_comment, 3)
        self.assertEqual(aux.weekly_threads, 0)
        self.assertEqual(aux.weekly_comment, 0)

    @override_settings(PLATFORM_NAME='Test')
    @override_settings(LMS_ROOT_URL='https://test.ts')
    @patch('eol_forum_notifications.views.get_block_info')
    @patch('eol_forum_notifications.utils.course_image_url')
    @patch('eol_forum_notifications.utils.get_course_by_id')
    def test_send_notifications_daily_no_users(self, course_mock, image_mock, block_mock):
        """
            test send_notifications() daily period when there isnt users
        """
        course_mock.side_effect = [namedtuple("Course", ["display_name_with_default", "end"])("this is a display name", None)]
        image_mock.return_value = '/assets/image.jpg'
        block_mock.return_value = {'display_name':'Test discussion xblock', 'parent': 'asdadssa'}
        self.discussion.daily_threads = 3
        self.discussion.daily_comment = 3
        self.discussion.weekly_threads = 3
        self.discussion.weekly_comment = 3
        self.discussion.save()
        self.assertEqual(self.discussion.daily_threads, 3)
        self.assertEqual(self.discussion.daily_comment, 3)
        self.assertEqual(self.discussion.weekly_threads, 3)
        self.assertEqual(self.discussion.weekly_comment, 3)
        send_notification('daily')
        aux = EolForumNotificationsDiscussions.objects.get(id=self.discussion.id)
        self.assertEqual(aux.daily_threads, 0)
        self.assertEqual(aux.daily_comment, 0)
        self.assertEqual(aux.weekly_threads, 3)
        self.assertEqual(aux.weekly_comment, 3)

    @override_settings(PLATFORM_NAME='Test')
    @override_settings(LMS_ROOT_URL='https://test.ts')
    @patch('eol_forum_notifications.views.get_block_info')
    @patch('eol_forum_notifications.utils.course_image_url')
    @patch('eol_forum_notifications.utils.get_course_by_id')
    def test_send_notifications_daily_empty_block_parents(self, course_mock, image_mock, block_mock):
        """
        Ensure that the send_notifications() function correctly skips blocks with an undefined parent (block['parent'] == ""), 
        logs the appropriate message, and does not raise any errors or continue processing that block.test send_notifications() 
        daily period when block have empty parents
        """
        course_mock.side_effect = [namedtuple("Course", ["display_name_with_default", "end"])("this is a display name", None)]
        image_mock.return_value = '/assets/image.jpg'
        block_mock.return_value = {'display_name':'Test discussion xblock', 'parent': ''}
        self.discussion.daily_threads = 3
        self.discussion.daily_comment = 3
        self.discussion.weekly_threads = 3
        self.discussion.weekly_comment = 3
        self.discussion.save()
        with self.assertLogs('eol_forum_notifications.views', level='INFO') as cm:
            send_notification('daily')
        self.assertTrue(any('INFO:eol_forum_notifications.views:EolForumNotification - Block id doesnt exists, block-v1:eol+test100+2021_1+type@eoldiscussion+block@5c13942678184cab9a5345b660292c6e, course: foo/baz/bar' in log for log in cm.output))

    @patch('eol_forum_notifications.views.get_current_site')
    @patch('eol_forum_notifications.views.get_block_info')
    @patch('eol_forum_notifications.utils.course_image_url')
    @patch('eol_forum_notifications.utils.get_course_by_id')
    def test_send_notifications_test_get_current_site(self, course_mock, image_mock, block_mock, mock_get_current_site):
        """
            Test send_notifications() ensuring that no error is logged when get_current_site() is patched to return a valid site configuration. 
            This confirms that the platform name and LMS URL are retrieved successfully and the exception handling path is not triggered.
        """
        config_values = {
            'PLATFORM_NAME': 'Test_2',
            'ROOT': 'https://test_2.ts'
        }
        # Use mock and make a dictionary
        mock_get_value = MagicMock(side_effect=lambda key, default=None: config_values.get(key, default))
        mock_site = MagicMock()
        mock_site.configuration.get_value = mock_get_value
        mock_get_current_site.return_value = mock_site
        
        course_mock.side_effect = [namedtuple("Course", ["display_name_with_default", "end"])("this is a display name", None)]
        image_mock.return_value = '/assets/image.jpg'
        block_mock.return_value = {'display_name':'Test discussion xblock', 'parent': 'parent_test'}
        self.discussion.daily_threads = 3
        self.discussion.daily_comment = 3
        self.discussion.weekly_threads = 3
        self.discussion.weekly_comment = 3
        self.discussion.save()
        with self.assertLogs('eol_forum_notifications.views', level='INFO') as cm:
            send_notification('daily')
        aux = EolForumNotificationsDiscussions.objects.get(id=self.discussion.id)
        self.assertEqual(aux.daily_threads, 0)
        self.assertFalse(any(
        'EolForumNotification - Error to get platform name and url site' in log
        for log in cm.output))

    @patch('eol_forum_notifications.utils.get_info_block_course')
    def test_save_notifications_get(self, block_course):
        """
            test save_notifications_get() normal process
        """
        block_course.return_value = {
            'course_name': 'course name',
            'discussion_name': 'discussion name'
        }
        user_notif = EolForumNotificationsUser.objects.create(discussion=self.discussion, user=self.student, how_often="daily")
        get_data = {
            'discussion_id': user_notif.discussion.discussion_id,
            'course_id': str(user_notif.discussion.course_id),
            'user_id': user_notif.user.id,
        }
        response = self.client.get(reverse('eol_discussion_notification:save_get'), get_data)
        request = response.request
        self.assertEqual(response.status_code, 200)
        self.assertEqual(request['PATH_INFO'], '/eol_discussion_notification/get_save/')

    def test_save_notifications_get_no_user_model(self):
        """
            test save_notifications_get() when user dont have eol-forum-notification-user model
        """
        get_data = {
            'discussion_id': self.discussion.discussion_id,
            'course_id': str(self.discussion.course_id),
            'user_id': self.student.id,
        }
        response = self.client.get(reverse('eol_discussion_notification:save_get'), get_data)
        request = response.request
        self.assertEqual(response.status_code, 404)

    def test_save_notifications_get_wrong_method(self):
        """
            test save_notifications_get() wrong method
        """
        get_data = {
            'discussion_id': self.discussion.discussion_id,
            'course_id': str(self.discussion.course_id),
            'user_id': self.student.id,
        }
        response = self.client.post(reverse('eol_discussion_notification:save_get'), get_data)
        request = response.request
        self.assertEqual(response.status_code, 400)

    def test_save_notifications_get_anonymous_user(self):
        """
            test save_notifications_get() with anonymous user
        """
        get_data = {
            'discussion_id': self.discussion.discussion_id,
            'course_id': str(self.discussion.course_id),
            'user_id': self.student.id,
        }
        client = Client()
        response = client.get(reverse('eol_discussion_notification:save_get'), get_data)
        request = response.request
        self.assertEqual(response.status_code, 302)

    def test_save_notifications_get_user_anonymous(self):
        """
        Tests save_notifications_get() when called by an anonymous user.
        Since the view is protected with @login_required, the function is tested directly
        without using reverse or making an HTTP request.
        """
        get_data = {
            'discussion_id': self.discussion.discussion_id,
            'course_id': str(self.discussion.course_id),
            'user_id': self.student.id,
        }
        request = TestRequest()
        request.method = 'GET'
        request.GET =  get_data
        request.user = AnonymousUser()
        response = save_notification_get(request)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content.decode(),'Inicie sesión y vuelva a presionar el link.')

    def test_save_notifications_get_wrong_user_id(self):
        """
            test save_notifications_get() when user id request is not equal to params user id
        """
        get_data = {
            'discussion_id': self.discussion.discussion_id,
            'course_id': str(self.discussion.course_id),
            'user_id': self.student2.id,
        }
        response = self.client.get(reverse('eol_discussion_notification:save_get'), get_data)
        request = response.request
        self.assertEqual(response.status_code, 404)

    def test_save_notifications_get_missing_params(self):
        """
            test save_notifications_get() when missing some params
        """
        get_data = {
            'discussion_id': self.discussion.discussion_id,
            'user_id': self.student.id,
        }
        response = self.client.get(reverse('eol_discussion_notification:save_get'), get_data)
        request = response.request
        self.assertEqual(response.status_code, 404)

    def test_save_notifications_post(self):
        """
            test save_notifications_post() normal process
        """
        post_data = {
            'discussion_id': self.discussion.discussion_id,
            'course_id': str(self.discussion.course_id),
            'user_id': self.student.id,
            'period': 'never'
        }
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = self.client.post(reverse('eol_discussion_notification:save_post'), post_data)
        request = response.request
        self.assertTrue(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(request['PATH_INFO'], '/eol_discussion_notification/post_save/')

    def test_save_notifications_post_wrong_method(self):
        """
            test save_notifications_post() wrong method
        """
        post_data = {
            'discussion_id': self.discussion.discussion_id,
            'course_id': str(self.discussion.course_id),
            'user_id': self.student.id,
            'period': 'never'
        }
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = self.client.get(reverse('eol_discussion_notification:save_post'), post_data)
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        self.assertEqual(response.status_code, 400)

    def test_save_notifications_post_missing_params(self):
        """
            test save_notifications_post() when missing some params
        """
        post_data = {
            'discussion_id': self.discussion.discussion_id,
            'course_id': str(self.discussion.course_id),
            'user_id': self.student.id
        }
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = self.client.post(reverse('eol_discussion_notification:save_post'), post_data)
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        self.assertEqual(response.status_code, 200)
        self.assertTrue("id=\"wrong_data\"" in response._container[0].decode())

    def test_save_notifications_post_user_anonymous(self):
        """
            test save_notifications_post() when user is anonymous
        """
        post_data = {
            'discussion_id': self.discussion.discussion_id,
            'course_id': str(self.discussion.course_id),
            'user_id': self.student.id,
            'period': 'never'
        }
        client = Client()
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = client.post(reverse('eol_discussion_notification:save_post'), post_data)
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        self.assertEqual(response.status_code, 302)

    @patch('eol_forum_notifications.views.render')
    def test_save_notifications_post_anonymous_user(self, mock_render):
        """
            save_notification_post() when user is anonymous and have an html as a response
        """
        mock_render.return_value = HttpResponse('Inicie sesión y vuelva a presionar el link.')
        post_data = {
            'discussion_id': self.discussion.discussion_id,
            'course_id': str(self.discussion.course_id),
            'user_id': self.student.id,
            'period': 'never'
        }
        request = HttpRequest()
        request.method = 'POST'
        request.POST =  post_data
        request.user = AnonymousUser()
        response = save_notification_post(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(),'Inicie sesión y vuelva a presionar el link.')
        mock_render.assert_called_with(
            request,
            'eol_forum_notifications/notification.html',
            {'error': 'Inicie sesión y vuelva a presionar el link del correo.'}
        )

    def test_save_notifications_post_user_id_wrong(self):
        """
            test save_notifications_post() when user id request is not equal to params user id
        """
        post_data = {
            'discussion_id': self.discussion.discussion_id,
            'course_id': str(self.discussion.course_id),
            'user_id': self.student2.id,
            'period': 'never'
        }
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = self.client.post(reverse('eol_discussion_notification:save_post'), post_data)
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        self.assertEqual(response.status_code, 200)
        self.assertTrue("id=\"wrong_data\"" in response._container[0].decode())

    def test_save_notifications_post_period_wrong(self):
        """
            test save_notifications_post() when period is wrong
        """
        post_data = {
            'discussion_id': self.discussion.discussion_id,
            'course_id': str(self.discussion.course_id),
            'user_id': self.student.id,
            'period': 'nevasdasdsaer'
        }
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = self.client.post(reverse('eol_discussion_notification:save_post'), post_data)
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        self.assertEqual(response.status_code, 200)
        self.assertTrue("id=\"wrong_data\"" in response._container[0].decode())

    def test_save_notifications_post_course_id_wrong(self):
        """
            test save_notifications_post() when course_id is wrong
        """
        post_data = {
            'discussion_id': self.discussion.discussion_id,
            'course_id': str('11111111111111111'),
            'user_id': self.student.id,
            'period': 'never'
        }
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = self.client.post(reverse('eol_discussion_notification:save_post'), post_data)
        self.assertFalse(EolForumNotificationsUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        self.assertEqual(response.status_code, 200)
        self.assertIn(' Un error inesperado ha ocurrido, por favor', response.content.decode())

    def test_utils_get_user_data_non_existing_discussion_id(self):
        """
        Test error when discussion_id doesn't exist
        """
        notifications=get_user_data('test_id', self.student, self.course.id, self.block_key)
        self.assertEqual(notifications, '{}')

    def test_utils_get_user_data_wrong_user_id(self):
        """
        Test error when user in notification is different from request user
        """
        user_notif = EolForumNotificationsUser.objects.create(discussion=self.discussion, user=self.student, how_often="daily")
        notifications=get_user_data('1234567890', self.student2, self.course.id, self.block_key)
        self.assertEqual(notifications, '{}')

    def test_utils_get_user_data(self):
        """
        Test get_user_data with expected path
        """
        user_notif = EolForumNotificationsUser.objects.create(discussion=self.discussion, user=self.student, how_often="daily")
        response=get_user_data('1234567890', self.student, self.course.id, self.block_key)
        response_data = json.loads(response)
        self.assertEqual(response_data['how_often'], 'daily')

    def test_utils_get_info_block_course_wrong_user_id(self):
        """
        Test error when user in notification is different from request user
        """
        info = get_info_block_course(self.discussion.id, 'course_test_wrong')
        self.assertEqual(info, None)

    @patch('eol_forum_notifications.utils.modulestore')
    def test_utils_get_block_info(self, mock_modulestore):
        """
        Test get_block_info with expected path
        """
        mock_block_key = MagicMock()
        mock_block_key.course_key = 'dummy-course-key'

        # Create a mock of the store and its methods
        mock_store = MagicMock()
        mock_block = MagicMock()
        mock_block.display_name = "title test"
        mock_block.parent = "parent-id"

        # Configure mocks
        mock_store.get_item.return_value = mock_block
        mock_modulestore.return_value = mock_store

        # Use context manager mock
        mock_store.bulk_operations.return_value.__enter__.return_value = None
        mock_store.bulk_operations.return_value.__exit__.return_value = None

        result = get_block_info(mock_block_key)
        expected = {
            'display_name': "title test",
            'parent': "parent-id"
        }
        self.assertEqual(result, expected)


class CommandTest(TestCase):
    @patch('eol_forum_notifications.management.commands.discussion_notification.send_notification')
    def test_command_discussion_notification(self,mock_send_notification):
        """
        Test discussion_notification
            1. Without how_often
            2. with wrong alternative to how_often
            3. Normal process
        """
        mock_send_notification.return_value = True
        out = StringIO()
        with self.assertRaises(CommandError):
            call_command('discussion_notification', stdout=out)
            self.assertTrue(out)
        with self.assertRaises(CommandError) as cm:
            call_command('discussion_notification','hourly', stdout=out)
        self.assertIn("EolForumNoticationsCommand - how_often must be 'weekly' or 'daily'", str(cm.exception))
        call_command('discussion_notification','daily', stdout=out)
        self.assertTrue(out)
