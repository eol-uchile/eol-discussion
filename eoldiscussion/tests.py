""" Tests for EolDiscussionXBlock"""
# Python Standard Libraries
from collections import namedtuple
from io import StringIO
import itertools
import json
import logging
import random
import string

# Installed packages (via pip)
from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command
from django.core.management.base import CommandError
from django.http import HttpRequest, HttpResponse
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from mock import patch, MagicMock, Mock
from safe_lxml import etree
from six.moves import range
import ddt
import mock

# Edx dependencies
from common.djangoapps.student.roles import CourseStaffRole
from common.djangoapps.student.tests.factories import UserFactory, CourseEnrollmentFactory
from common.djangoapps.util.testing import UrlResetMixin
from opaque_keys.edx.keys import UsageKey
from opaque_keys.edx.locator import CourseLocator
from xblock.field_data import DictFieldData
from xblock.fields import NO_CACHE_VALUE, UNIQUE_ID, ScopeIds
from xblock.runtime import Runtime
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

# Internal project dependencies
from eoldiscussion.eoldiscussion import EolDiscussionXBlock
from eoldiscussion.eolgradediscussion import EolGradeDiscussionXBlock
from eoldiscussion.models import EolDiscussionXBlockNotificationUser, EolDiscussionXBlockNotification
from eoldiscussion.utils import get_user_data, get_info_block_course, get_block_info
from eoldiscussion.views import send_notification, save_notification, save_notification_get, save_notification_post


logger = logging.getLogger(__name__)

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

    @patch("eoldiscussion.eoldiscussion.EolDiscussionXBlock.load_definition_xml")
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


    @patch("eoldiscussion.eoldiscussion.EolDiscussionXBlock.load_definition_xml")
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

    def test_studio_view_render_eol_discussion(self,):
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

    def test_author_view_render_eol_discussion(self):
        """
            Check if author view is rendering
        """
        author_view = self.xblock.author_view()
        author_view_html = author_view.content
        self.assertIn('Contenido Studio', author_view_html)

    @override_settings(USER_API_DEFAULT_PREFERENCES={'time_zone':'America/Santiago'})
    @patch('lms.djangoapps.discussion.django_comment_client.permissions.has_permission', return_value=True)
    def test_student_view_render_eol_discussion(self,_):
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


class TestNotifiactionsDiscussion(UrlResetMixin, ModuleStoreTestCase):

    def setUp(self):
        super(TestNotifiactionsDiscussion, self).setUp()
        self.course = CourseFactory.create(org='foo', course='baz', run='bar')
        self.block_key = UsageKey.from_string('block-v1:eol+test100+2021_1+type@eoldiscussion+block@5c13942678184cab9a5345b660292c6e')
        self.discussion = EolDiscussionXBlockNotification.objects.create(
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

    def test_EolDiscussionXBlockNotification_str_function(self):
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
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = self.client.post(
            reverse('eol_discussion_notification:save'), post_data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        notif = EolDiscussionXBlockNotificationUser.objects.get(user=self.student, discussion=self.discussion)
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
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = client_anonymous.post(
            reverse('eol_discussion_notification:save'), post_data)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())

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
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = self.client.get(
            reverse('eol_discussion_notification:save'), post_data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())

    def test_save_notifications_wrong_params(self):
        """
            save_notifications() when missing a params request
        """
        post_data = {
            'discussion_id': 'ecedb9f8c633496d3fc4bd014ee30a65c75796f2',
            'course_id': str(self.course.id),
            'user_id': str(self.student.id)
        }
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = self.client.post(
            reverse('eol_discussion_notification:save'), post_data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())

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
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = self.client.post(
            reverse('eol_discussion_notification:save'), post_data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())

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
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = self.client.post(
            reverse('eol_discussion_notification:save'), post_data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())

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
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = self.client.post(
            reverse('eol_discussion_notification:save'), post_data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())

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
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=post_data['discussion_id']).exists())
        response = self.client.post(
            reverse('eol_discussion_notification:save'), post_data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=post_data['discussion_id']).exists())

    @override_settings(PLATFORM_NAME='Test')
    @override_settings(LMS_ROOT_URL='https://test.ts')
    @patch('eoldiscussion.views.get_block_info')
    @patch('eoldiscussion.utils.course_image_url')
    @patch('eoldiscussion.utils.get_course_by_id')
    def test_send_notifications_daily(self, course_mock, image_mock, block_mock):
        """
            test send_notifications() daily period
        """
        course_mock.side_effect = [namedtuple("Course", ["display_name_with_default", "end"])("this is a display name", None)]
        image_mock.return_value = '/assets/image.jpg'
        block_mock.return_value = {'display_name':'Test discussion xblock', 'parent': 'asdadssa'}
        user_notif = EolDiscussionXBlockNotificationUser.objects.create(discussion=self.discussion, user=self.student, how_often="daily")
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
        aux = EolDiscussionXBlockNotification.objects.get(id=self.discussion.id)
        self.assertEqual(aux.daily_threads, 0)
        self.assertEqual(aux.daily_comment, 0)
        self.assertEqual(aux.weekly_threads, 3)
        self.assertEqual(aux.weekly_comment, 3)

    @override_settings(PLATFORM_NAME='Test')
    @override_settings(LMS_ROOT_URL='https://test.ts')
    @patch('eoldiscussion.views.get_block_info')
    @patch('eoldiscussion.utils.course_image_url')
    @patch('eoldiscussion.utils.get_course_by_id')
    def test_send_notifications_weekly(self, course_mock, image_mock, block_mock):
        """
            test send_notifications() weekly period
        """
        course_mock.side_effect = [namedtuple("Course", ["display_name_with_default", "end"])("this is a display name", None)]
        image_mock.return_value = '/assets/image.jpg'
        block_mock.return_value = {'display_name':'Test discussion xblock', 'parent': 'asdadssa'}
        user_notif = EolDiscussionXBlockNotificationUser.objects.create(discussion=self.discussion, user=self.student, how_often="daily")
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
        aux = EolDiscussionXBlockNotification.objects.get(id=self.discussion.id)
        self.assertEqual(aux.daily_threads, 3)
        self.assertEqual(aux.daily_comment, 3)
        self.assertEqual(aux.weekly_threads, 0)
        self.assertEqual(aux.weekly_comment, 0)

    @override_settings(PLATFORM_NAME='Test')
    @override_settings(LMS_ROOT_URL='https://test.ts')
    @patch('eoldiscussion.views.get_block_info')
    @patch('eoldiscussion.utils.course_image_url')
    @patch('eoldiscussion.utils.get_course_by_id')
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
        aux = EolDiscussionXBlockNotification.objects.get(id=self.discussion.id)
        self.assertEqual(aux.daily_threads, 0)
        self.assertEqual(aux.daily_comment, 0)
        self.assertEqual(aux.weekly_threads, 3)
        self.assertEqual(aux.weekly_comment, 3)

    @override_settings(PLATFORM_NAME='Test')
    @override_settings(LMS_ROOT_URL='https://test.ts')
    @patch('eoldiscussion.views.get_block_info')
    @patch('eoldiscussion.utils.course_image_url')
    @patch('eoldiscussion.utils.get_course_by_id')
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
        with self.assertLogs('eoldiscussion.views', level='INFO') as cm:
            send_notification('daily')
        self.assertTrue(any('INFO:eoldiscussion.views:EolForumNotification - Block id doesnt exists, block-v1:eol+test100+2021_1+type@eoldiscussion+block@5c13942678184cab9a5345b660292c6e, course: foo/baz/bar' in log for log in cm.output))

    @patch('eoldiscussion.views.get_current_site')
    @patch('eoldiscussion.views.get_block_info')
    @patch('eoldiscussion.utils.course_image_url')
    @patch('eoldiscussion.utils.get_course_by_id')
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
        with self.assertLogs('eoldiscussion.views', level='INFO') as cm:
            send_notification('daily')
        aux = EolDiscussionXBlockNotification.objects.get(id=self.discussion.id)
        self.assertEqual(aux.daily_threads, 0)
        self.assertFalse(any(
        'EolForumNotification - Error to get platform name and url site' in log
        for log in cm.output))

    @patch('eoldiscussion.utils.get_info_block_course')
    def test_save_notifications_get(self, block_course):
        """
            test save_notifications_get() normal process
        """
        block_course.return_value = {
            'course_name': 'course name',
            'discussion_name': 'discussion name'
        }
        user_notif = EolDiscussionXBlockNotificationUser.objects.create(discussion=self.discussion, user=self.student, how_often="daily")
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
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = self.client.post(reverse('eol_discussion_notification:save_post'), post_data)
        request = response.request
        self.assertTrue(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())
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
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = self.client.get(reverse('eol_discussion_notification:save_post'), post_data)
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())
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
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = self.client.post(reverse('eol_discussion_notification:save_post'), post_data)
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())
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
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = client.post(reverse('eol_discussion_notification:save_post'), post_data)
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        self.assertEqual(response.status_code, 302)

    @patch('eoldiscussion.views.render')
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
            'eoldiscussion/notification.html',
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
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = self.client.post(reverse('eol_discussion_notification:save_post'), post_data)
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())
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
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = self.client.post(reverse('eol_discussion_notification:save_post'), post_data)
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())
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
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())
        response = self.client.post(reverse('eol_discussion_notification:save_post'), post_data)
        self.assertFalse(EolDiscussionXBlockNotificationUser.objects.filter(user=self.student, discussion=self.discussion).exists())
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
        user_notif = EolDiscussionXBlockNotificationUser.objects.create(discussion=self.discussion, user=self.student, how_often="daily")
        notifications=get_user_data('1234567890', self.student2, self.course.id, self.block_key)
        self.assertEqual(notifications, '{}')

    def test_utils_get_user_data(self):
        """
        Test get_user_data with expected path
        """
        user_notif = EolDiscussionXBlockNotificationUser.objects.create(discussion=self.discussion, user=self.student, how_often="daily")
        response=get_user_data('1234567890', self.student, self.course.id, self.block_key)
        response_data = json.loads(response)
        self.assertEqual(response_data['how_often'], 'daily')

    def test_utils_get_info_block_course_wrong_user_id(self):
        """
        Test error when user in notification is different from request user
        """
        info = get_info_block_course(self.discussion.id, 'course_test_wrong')
        self.assertEqual(info, None)

    @patch('eoldiscussion.utils.modulestore')
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
    @patch('eoldiscussion.management.commands.discussion_notification.send_notification')
    def test_command_discussion_notification(self,mock_send_notification):
        """
        Test discussion_notification
            1. Without how_often
            2. with wrong alternative to how_often
            3. Normal process
        """
        mock_send_notification.return_value = True
        out = StringIO()
        with self.assertRaises(CommandError) as cm:
            call_command('discussion_notification','hourly', stdout=out)
        self.assertIn("EolForumNoticationsCommand - how_often must be 'weekly' or 'daily'", str(cm.exception))
        call_command('discussion_notification','daily', stdout=out)
        self.assertTrue(out)


class TestGradeForum(UrlResetMixin, ModuleStoreTestCase):
    def make_an_xblock(cls, **kw):
        """
        Helper method that creates a EolGradeForum XBlock
        """

        course = cls.course
        runtime = Mock(
            course_id=course.id,
            user_is_staff=False,
            service=Mock(
                return_value=Mock(_catalog={}),
            ),
        )
        scope_ids = Mock()
        field_data = DictFieldData(kw)
        xblock = EolGradeDiscussionXBlock(runtime, field_data, scope_ids)
        xblock.xmodule_runtime = runtime
        xblock.location = course.location
        xblock.course_id = course.id
        xblock.category = 'eolforumdiscussion'
        return xblock

    def setUp(self):
        """
        Creates an xblock
        """
        super(TestGradeForum, self).setUp()
        self.course = CourseFactory.create(org='foo', course='baz', run='bar')

        self.xblock = self.make_an_xblock()

        with patch('common.djangoapps.student.models.cc.User.save'):
            # Create the student
            self.student = UserFactory(
                username='student',
                password='test',
                email='student@edx.org')
            # Enroll the student in the course
            CourseEnrollmentFactory(
                user=self.student, course_id=self.course.id)

            # Create staff user
            self.staff_user = UserFactory(
                username='staff_user',
                password='test',
                email='staff@edx.org')
            CourseEnrollmentFactory(
                user=self.staff_user,
                course_id=self.course.id)
            CourseStaffRole(self.course.id).add_users(self.staff_user)

    def test_validate_field_data(self):
        """
            Verify if default xblock is created correctly
        """
        self.assertEqual(self.xblock.display_name, 'Participación Foro')
        self.assertEqual(self.xblock.puntajemax, 100)
        self.assertEqual(self.xblock.id_forum, '')

    def test_edit_block_studio(self):
        """
            Verify submit studio edits is working
        """
        request = TestRequest()
        request.method = 'POST'
        self.xblock.xmodule_runtime.user_is_staff = True
        data = json.dumps({'display_name': 'testname',
                           "puntajemax": '200', "id_forum": 'test_id'})
        request.body = data.encode()
        response = self.xblock.studio_submit(request)
        self.assertEqual(self.xblock.display_name, 'testname')
        self.assertEqual(self.xblock.puntajemax, 200)
        self.assertEqual(self.xblock.id_forum, 'test_id')
    
    def test_edit_block_studio_wrong_data(self):
        """
            Verify submit studio edits is working when puntajemax is wrong
        """
        request = TestRequest()
        request.method = 'POST'
        self.xblock.xmodule_runtime.user_is_staff = True
        data = json.dumps({'display_name': 'testname',
                           "puntajemax": '-200', "id_forum": 'test_id'})
        request.body = data.encode()
        response = self.xblock.studio_submit(request)
        self.assertEqual(
            response.json_body['result'],
            'error'
        )

    def test_student_view_staff(self):
        """
            Verify context in student_view staff user
        """
        self.xblock.xmodule_runtime.user_is_staff = True
        self.xblock.scope_ids.user_id = self.staff_user.id
        response = self.xblock.get_context()
        self.assertEqual(response['is_course_staff'], True)
        self.assertEqual(response['calificado'], 0)
        self.assertEqual(response['total_student'], 2)

    def test_student_view_student(self):
        """
            Verify context in student_view student user
        """
        self.xblock.xmodule_runtime.user_is_staff = False
        self.xblock.scope_ids.user_id = self.student.id
        response = self.xblock.get_context()
        self.assertEqual(response['is_course_staff'], False)
        self.assertEqual(response['puntaje'], '')
        self.assertEqual(response['feedback'], '')

    @patch('lms.djangoapps.grades.signals.handlers.PROBLEM_WEIGHTED_SCORE_CHANGED.send')
    def test_save_staff_user(self, _):
        """
          Save score by staff user
        """

        request = TestRequest()
        request.method = 'POST'

        self.xblock.xmodule_runtime.user_is_staff = True
        self.xblock.scope_ids.user_id = self.staff_user.id
        datos = [{'user_id': self.student.id, 'score': "11", 'feedback': ''},
                 {'user_id': self.staff_user.id, 'score': "22", 'feedback': ''}]
        data = json.dumps({"data": datos})
        request.body = data.encode()

        response = self.xblock.savestudentanswersall(request)
        self.assertEqual(self.xblock.get_score(self.student.id), 11)
        self.assertEqual(self.xblock.get_score(self.staff_user.id), 22)
        response = self.xblock.get_context()
        self.assertEqual(response['is_course_staff'], True)
        self.assertEqual(response['calificado'], 2)
        self.assertEqual(response['total_student'], 2)

    @patch('lms.djangoapps.grades.signals.handlers.PROBLEM_WEIGHTED_SCORE_CHANGED.send')
    def test_save_student_user(self, _):
        """
          Save score by student user
        """

        request = TestRequest()
        request.method = 'POST'

        self.xblock.xmodule_runtime.user_is_staff = False

        self.xblock.scope_ids.user_id = self.student.id
        datos = [{'user_id': self.student.id, 'score': "11", 'feedback': ''},
                 {'user_id': self.staff_user.id, 'score': "22", 'feedback': ''}]
        data = json.dumps({"data": datos})
        request.body = data.encode()
        response = self.xblock.savestudentanswersall(request)
        data_response = json.loads(response._app_iter[0].decode())
        self.assertEqual(data_response['result'], 'error')
        response = self.xblock.get_context()
        self.assertEqual(response['is_course_staff'], False)
        self.assertEqual(response['puntaje'], '')

    def test_wrong_data_staff_user(self):
        """
          Save score by staff user with wrong score
        """

        request = TestRequest()
        request.method = 'POST'

        self.xblock.xmodule_runtime.user_is_staff = True
        self.xblock.scope_ids.user_id = self.staff_user.id
        datos = [{'user_id': self.student.id, 'score': "asd1", 'feedback': ''},
                 {'user_id': self.staff_user.id, 'score': "22", 'feedback': ''}]
        data = json.dumps({"data": datos})
        request.body = data.encode()
        response = self.xblock.savestudentanswersall(request)
        data_response = json.loads(response._app_iter[0].decode())
        self.assertEqual(data_response['result'], 'error')

    @patch('lms.djangoapps.grades.signals.handlers.PROBLEM_WEIGHTED_SCORE_CHANGED.send')
    def test_save_student_score_max_score(self, _):
        """
          Save score by staff user with score = max score
        """

        request = TestRequest()
        request.method = 'POST'

        self.xblock.xmodule_runtime.user_is_staff = True
        self.xblock.scope_ids.user_id = self.staff_user.id
        datos = [{'user_id': self.student.id, 'score': "100", 'feedback': ''},
                 {'user_id': self.staff_user.id, 'score': "100", 'feedback': ''}]
        data = json.dumps({"data": datos})
        request.body = data.encode()
        response = self.xblock.savestudentanswersall(request)
        self.assertEqual(self.xblock.get_score(self.student.id), 100)
        self.assertEqual(self.xblock.get_score(self.staff_user.id), 100)

    @patch('lms.djangoapps.grades.signals.handlers.PROBLEM_WEIGHTED_SCORE_CHANGED.send')
    def test_save_staff_user_with_feedback(self, _):
        """
          Save score by staff user with feedback
        """

        request = TestRequest()
        request.method = 'POST'

        self.xblock.xmodule_runtime.user_is_staff = True
        self.xblock.scope_ids.user_id = self.staff_user.id
        datos = [{'user_id': self.student.id, 'score': "11", 'feedback':'this is a comment'},
                 {'user_id': self.staff_user.id, 'score': "22", 'feedback':'this is a comment part 2'}]
        data = json.dumps({"data": datos})
        request.body = data.encode()

        response = self.xblock.savestudentanswersall(request)
        self.assertEqual(self.xblock.get_score(self.student.id), 11)
        self.assertEqual(self.xblock.get_score(self.staff_user.id), 22)
        self.xblock.xmodule_runtime.user_is_staff = False
        self.xblock.scope_ids.user_id = self.student.id
        response = self.xblock.get_context()
        self.assertEqual(response['is_course_staff'], False)
        self.assertEqual(response['puntaje'], 11)
        self.assertEqual(response['feedback'], 'this is a comment')

    @patch('lms.djangoapps.grades.signals.handlers.PROBLEM_WEIGHTED_SCORE_CHANGED.send')
    def test_save_student_score_min_score(self, _):
        """
          Save score by staff user with score = 0
        """

        request = TestRequest()
        request.method = 'POST'

        self.xblock.xmodule_runtime.user_is_staff = True
        self.xblock.scope_ids.user_id = self.staff_user.id
        datos = [{'user_id': self.student.id, 'score': "0", 'feedback': ''},
                 {'user_id': self.staff_user.id, 'score': "0", 'feedback': ''}]
        data = json.dumps({"data": datos})
        request.body = data.encode()
        response = self.xblock.savestudentanswersall(request)
        self.assertEqual(self.xblock.get_score(self.student.id), 0)
        self.assertEqual(self.xblock.get_score(self.staff_user.id), 0)

    def test_save_student_score_min_score_wrong_less_than_zero(self):
        """
          Save score by staff user with score < 0
        """

        request = TestRequest()
        request.method = 'POST'

        self.xblock.xmodule_runtime.user_is_staff = True
        self.xblock.scope_ids.user_id = self.staff_user.id
        datos = [{'user_id': self.student.id, 'score': "-10", 'feedback': ''}]
        data = json.dumps({"data": datos})
        request.body = data.encode()
        response = self.xblock.savestudentanswersall(request)
        data_response = json.loads(response._app_iter[0].decode())
        self.assertEqual(data_response['result'], 'error')

    def test_save_student_score_min_score_wrong(self):
        """
          Save score by staff user with score > max score
        """

        request = TestRequest()
        request.method = 'POST'

        self.xblock.xmodule_runtime.user_is_staff = True
        self.xblock.scope_ids.user_id = self.staff_user.id
        datos = [{'user_id': self.student.id, 'score': "101", 'feedback': ''}]
        data = json.dumps({"data": datos})
        request.body = data.encode()
        response = self.xblock.savestudentanswersall(request)
        data_response = json.loads(response._app_iter[0].decode())
        self.assertEqual(data_response['result'], 'error')

    def test_get_data_forum_no_course_staff(self):
        """
          test get_data_forum when user is not course staff
        """
        request = TestRequest()
        request.method = 'POST'
        data = json.dumps({})
        request.body = data.encode()

        self.xblock.xmodule_runtime.user_is_staff = False
        self.xblock.scope_ids.user_id = self.student.id
        self.xblock.id_forum = 'adsadad'
        response = self.xblock.get_data_forum(request)
        data_response = json.loads(response._app_iter[0].decode())
        self.assertEqual(data_response['result'], 'user is not course staff')

    @patch('openedx.core.djangoapps.django_comment_common.models.ForumsConfig.current')
    @patch('requests.request')
    def test_get_data_forum(self, get, _):
        """
          test get_data_forum normal process
        """
        collection = [
            {
                "comments_count": 5,
                "user_id": str(self.staff_user.id),
                "created_at": "2020-11-10T18:51:04Z",
                "username": "test1",
                "unread_comments_count": 1,
                "commentable_id": "course",
                "anonymous_to_peers": False,
                "closed": False,
                "pinned": False,
                "updated_at": "2020-11-23T15:44:49Z",
                "course_id": "course-v1:eol+test101+2020",
                "id": "5faae1182f1f5e001b09d32a",
                "anonymous": False,
                "context": "course",
                "title": "asdasd",
                "votes": {},
                "abuse_flaggers": [],
                "read":False,
                "type":"thread",
                "thread_type":"question",
                "at_position_list":[],
                "endorsed":True,
                "last_activity_at":"2020-11-23T15:44:49Z",
                "body":"asdasd"
            },
            {
                "comments_count": 0,
                "user_id": str(self.student.id),
                "created_at": "2020-11-23T14:54:32Z",
                "username": "test2",
                "unread_comments_count": 0,
                "commentable_id": "course",
                "anonymous_to_peers": False,
                "closed": False,
                "pinned": False,
                "updated_at": "2020-11-23T14:54:32Z",
                "course_id": "course-v1:eol+test101+2020",
                "id": "5fbbcd282f1f5e001a0740c4",
                "anonymous": True,
                "context": "course",
                "title": "asdasd",
                "votes": {},
                "abuse_flaggers": [],
                "read":True,
                "type":"thread",
                "thread_type":"discussion",
                "at_position_list":[],
                "endorsed":False,
                "last_activity_at":"2020-11-23T14:54:32Z",
                "body":"asdaseda"
            }]
        data_all_thread = {"page": 1, "num_pages": 1, "collection": collection}
        data_thread_1 = {
            "comments_count": 3,
            "non_endorsed_resp_total": 1,
            "user_id": str(self.staff_user.id),
            "non_endorsed_responses": [
                {
                    "anonymous": False,
                    "body": "asd",
                    "user_id": str(self.student.id),
                    "thread_id": "5faae1182f1f5e001b09d32a",
                    "username": "test2",
                    "children": [
                            {
                                "anonymous": False,
                                "body": "o mantequilla",
                                "parent_id": "5faae14a2f1f5e001b09d32d",
                                "user_id": str(self.staff_user.id),
                                "created_at": "2020-11-10T18:52:01Z",
                                "username": "test1",
                                "children": [],
                                "depth":1,
                                "commentable_id":"course",
                                "anonymous_to_peers":False,
                                "closed":False,
                                "votes":{},
                                "updated_at": "2020-11-10T18:52:01Z",
                                "at_position_list": [],
                                "endorsed":False,
                                "course_id":"course-v1:eol+test101+2020",
                                "abuse_flaggers":[],
                                "thread_id":"5faae1182f1f5e001b09d32a",
                                "id":"5faae1512f1f5e001b09d32e",
                                "type":"comment"
                            }
                    ],
                    "depth":0,
                    "commentable_id":"course",
                    "anonymous_to_peers":False,
                    "closed":False,
                    "votes":{},
                    "updated_at": "2020-11-10T18:51:54Z",
                    "at_position_list": [],
                    "endorsed":False,
                    "course_id":"course-v1:eol+test101+2020",
                    "abuse_flaggers":[],
                    "created_at":"2020-11-10T18:51:54Z",
                    "id":"5faae14a2f1f5e001b09d32d",
                    "type":"comment"
                }
            ],
            "resp_limit": 200,
            "created_at": "2020-11-10T18:51:04Z",
            "username": "test1",
            "unread_comments_count": 0,
            "commentable_id": "ecedb9f8c633496d3fc4bd014ee30a65c75796f2",
            "anonymous_to_peers": False,
            "closed": False,
            "pinned": False,
            "updated_at": "2020-11-23T15:44:49Z",
            "resp_total": 2,
            "course_id": "course-v1:eol+test101+2020",
            "id": "5faae1182f1f5e001b09d32a",
            "anonymous": False,
            "body": "d1",
            "endorsed_responses": [
                    {
                        "anonymous": False,
                        "body": "asdf",
                        "user_id": str(self.student.id),
                        "thread_id": "5faae1182f1f5e001b09d32a",
                        "username": "test2",
                        "children": [
                            {
                                "anonymous": False,
                                "body": "o asdasd",
                                "parent_id": "5faae1392f1f5e001b09d32b",
                                "user_id": str(self.staff_user.id),
                                "created_at": "2020-11-10T18:51:45Z",
                                "username": "test1",
                                "children": [],
                                "depth":1,
                                "commentable_id":"course",
                                "anonymous_to_peers":False,
                                "closed":False,
                                "votes":{},
                                "updated_at": "2020-11-10T18:51:45Z",
                                "at_position_list": [],
                                "endorsed":False,
                                "course_id":"course-v1:eol+test101+2020",
                                "abuse_flaggers":[],
                                "thread_id":"5faae1182f1f5e001b09d32a",
                                "id":"5faae1412f1f5e001b09d32c",
                                "type":"comment"
                            },
                            {
                                "anonymous": False,
                                "body": "ola soy test2",
                                "parent_id": "5faae1392f1f5e001b09d32b",
                                "user_id": str(self.student.id),
                                "created_at": "2020-11-23T15:44:49Z",
                                "username": "test2",
                                "children": [],
                                "depth":1,
                                "commentable_id":"course",
                                "anonymous_to_peers":False,
                                "closed":False,
                                "votes":{},
                                "updated_at": "2020-11-23T15:44:49Z",
                                "at_position_list": [],
                                "endorsed":False,
                                "course_id":"course-v1:eol+test101+2020",
                                "abuse_flaggers":[],
                                "thread_id":"5faae1182f1f5e001b09d32a",
                                "id":"5fbbd8f12f1f5e001a0740c5",
                                "type":"comment"
                            }
                        ],
                        "depth":0,
                        "endorsement":{},
                        "commentable_id": "course",
                        "anonymous_to_peers": False,
                        "closed": False,
                        "votes": {},
                        "updated_at": "2020-11-10T18:58:28Z",
                        "at_position_list": [],
                        "endorsed":True,
                        "course_id":"course-v1:eol+test101+2020",
                        "abuse_flaggers":[],
                        "created_at":"2020-11-10T18:51:37Z",
                        "id":"5faae1392f1f5e001b09d32b",
                        "type":"comment"
                    }
            ],
            "context": "course",
            "title": "p1",
            "votes": {},
            "abuse_flaggers": [],
            "read": True,
            "type": "thread",
            "thread_type": "question",
            "at_position_list": [],
            "endorsed": True,
            "last_activity_at": "2020-11-23T15:44:49Z",
            "resp_skip": 0
        }
        data_thread_2 = {"comments_count": 2,
                         "user_id": str(self.student.id),
                         "resp_limit": 200,
                         "title": "p2",
                         "created_at": "2020-11-16T17:49:47Z",
                         "username": "test2",
                         "unread_comments_count": 0,
                         "commentable_id": "ecedb9f8c633496d3fc4bd014ee30a65c75796f2",
                         "anonymous_to_peers": False,
                         "closed": False,
                         "pinned": False,
                         "updated_at": "2020-11-20T14:45:06Z",
                         "resp_total": 1,
                         "course_id": "course-v1:eol+test101+2020",
                         "id": "5fbbcd282f1f5e001a0740c4",
                         "anonymous": True,
                         "body": "d2",
                         "context": "course",
                         "children": [{"anonymous": False,
                                       "body": "shajdkhsajkdhsajd",
                                       "user_id": str(self.student.id),
                                       "thread_id": "5fbbcd282f1f5e001a0740c4",
                                       "username": "test1",
                                       "children": [{"anonymous": False,
                                                     "body": "hsajdhjsakd",
                                                     "parent_id": "5fb71232132130019e5c0d1",
                                                     "user_id": str(self.staff_user.id),
                                                     "created_at": "2020-11-20T14:45:06Z",
                                                     "username": "test2",
                                                     "children": [],
                                                     "depth":1,
                                                     "commentable_id":"ecedb9f8c633496d3fc4bd014ee30a65c75796f2",
                                                     "anonymous_to_peers":False,
                                                     "closed":False,
                                                     "votes":{},
                                                     "updated_at": "2020-11-20T14:45:06Z",
                                                     "at_position_list": [],
                                                     "endorsed":False,
                                                     "course_id":"course-v1:eol+test101+2020",
                                                     "abuse_flaggers":[],
                                                     "thread_id":"5fbbcd282f1f5e001a0740c4",
                                                     "id":"5fb7d6214231245e0019e5c0d2",
                                                     "type":"comment"}],
                                       "depth":0,
                                       "commentable_id":"ecedb9f8c633496d3fc4bd014ee30a65c75796f2",
                                       "anonymous_to_peers":False,
                                       "closed":False,
                                       "votes":{},
                                       "updated_at": "2020-11-20T14:44:56Z",
                                       "at_position_list": [],
                                       "endorsed":False,
                                       "course_id":"course-v1:eol+test101+2020",
                                       "abuse_flaggers":[],
                                       "created_at":"2020-11-20T14:44:56Z",
                                       "id":"5fb71232132130019e5c0d1",
                                       "type":"comment"}],
                         "votes": {},
                         "abuse_flaggers": [],
                         "courseware_title": "Week 1 / Topic-Level Student-Visible Label",
                         "read": True,
                         "type": "thread",
                         "thread_type": "discussion",
                         "at_position_list": [],
                         "endorsed": False,
                         "last_activity_at": "2020-11-20T14:45:06Z",
                         "courseware_url": "/courses/course-v1:eol+test101+2020/jump_to/block-v1:eol+test101+2020+type@discussion+block@62b0a5dfbecb4738806620e2d4964a12",
                         "resp_skip": 0}
        get.side_effect = [
            namedtuple(
                "Request", [
                    "status_code", "json"])(
                200, lambda:data_all_thread),
            namedtuple(
                "Request", [
                    "status_code", "json"])(
                200, lambda:data_thread_1),
            namedtuple(
                "Request", [
                    "status_code", "json"])(
                200, lambda:data_thread_2), ]

        request = TestRequest()
        request.method = 'POST'
        data = json.dumps({})
        request.body = data.encode()

        self.xblock.xmodule_runtime.user_is_staff = True
        self.xblock.scope_ids.user_id = self.staff_user.id
        self.xblock.id_forum = 'adsadad'
        from lms.djangoapps.courseware.models import StudentModule
        module = StudentModule(
            module_state_key=self.xblock.location,
            student_id=self.student.id,
            course_id=self.course.id,
            state=json.dumps({"feedback": "comentario121"}))
        module.save()
        response = self.xblock.get_data_forum(request)
        data_response = json.loads(response._app_iter[0].decode())

        self.assertEqual(data_response['result'], 'success')
        lista_alumnos = [
            {
                'id': self.staff_user.id,
                'username': self.staff_user.username,
                'correo': self.staff_user.email,
                'score': '',
                'feedback': '',
                'student_forum': {
                    "5faae1182f1f5e001b09d32a": {},
                    "5fbbcd282f1f5e001a0740c4": {
                        "5fb71232132130019e5c0d1": ["5fb7d6214231245e0019e5c0d2"]}}},
            {
                'id': self.student.id,
                'username': self.student.username,
                'correo': self.student.email,
                    'score': '',
                    'feedback': 'comentario121',
                    'student_forum': {
                        '5fbbcd282f1f5e001a0740c4': {},
                        '5faae1182f1f5e001b09d32a': {
                            '5faae14a2f1f5e001b09d32d': [],
                             '5faae1392f1f5e001b09d32b': []}}}]
        self.assertEqual(data_response['lista_alumnos'], lista_alumnos)

    @patch('openedx.core.djangoapps.django_comment_common.models.ForumsConfig.current')
    @patch('requests.request')
    def test_get_data_forum_fail_get_thread(self, get, _):
        """
          test get_data_forum fail to get all threads
        """
        collection = []
        data_all_thread = {"page": 1, "num_pages": 1, "collection": collection}
        get.side_effect = [
            namedtuple(
                "Request", [
                    "status_code", "text"])(
                400, data_all_thread),
        ]

        request = TestRequest()
        request.method = 'POST'
        data = json.dumps({})
        request.body = data.encode()

        self.xblock.xmodule_runtime.user_is_staff = True
        self.xblock.scope_ids.user_id = self.staff_user.id
        self.xblock.id_forum = 'adsadad'
        response = self.xblock.get_data_forum(request)
        data_response = json.loads(response._app_iter[0].decode())
        self.assertEqual(data_response['result'], 'error')

    @patch('openedx.core.djangoapps.django_comment_common.models.ForumsConfig.current')
    @patch('requests.request')
    def test_get_data_forum_no_threads(self, get, _):
        """
          test get_data_forum when id_discussion dont have threads
        """
        collection = []
        data_all_thread = {"page": 1, "num_pages": 1, "collection": collection}
        get.side_effect = [
            namedtuple(
                "Request", [
                    "status_code", "json"])(
                200, lambda:data_all_thread),
        ]

        request = TestRequest()
        request.method = 'POST'
        data = json.dumps({})
        request.body = data.encode()

        self.xblock.xmodule_runtime.user_is_staff = True
        self.xblock.scope_ids.user_id = self.staff_user.id
        self.xblock.id_forum = 'adsadad'
        response = self.xblock.get_data_forum(request)
        data_response = json.loads(response._app_iter[0].decode())
        self.assertEqual(data_response['result'], 'no data')

    @patch('openedx.core.djangoapps.django_comment_common.models.ForumsConfig.current')
    @patch('requests.request')
    def test_get_data_forum_no_id_forum(self, get, _):
        """
          test get_data_forum without set id_forum
        """
        collection = []
        data_all_thread = {"page": 1, "num_pages": 1, "collection": collection}
        get.side_effect = [
            namedtuple(
                "Request", [
                    "status_code", "json"])(
                200, lambda:data_all_thread),
        ]

        request = TestRequest()
        request.method = 'POST'
        data = json.dumps({})
        request.body = data.encode()

        self.xblock.xmodule_runtime.user_is_staff = True
        self.xblock.scope_ids.user_id = self.staff_user.id
        response = self.xblock.get_data_forum(request)
        data_response = json.loads(response._app_iter[0].decode())
        self.assertEqual(data_response['result'], 'no id_forum')

    @patch('openedx.core.djangoapps.django_comment_common.models.ForumsConfig.current')
    @patch('requests.request')
    def test_get_data_forum_fail_get_comment(self, get, _):
        """
          test get all threads and failed to get comments
        """
        collection = [
            {
                "comments_count": 5,
                "user_id": str(self.staff_user.id),
                "created_at": "2020-11-10T18:51:04Z",
                "username": "test1",
                "unread_comments_count": 1,
                "commentable_id": "course",
                "anonymous_to_peers": False,
                "closed": False,
                "pinned": False,
                "updated_at": "2020-11-23T15:44:49Z",
                "course_id": "course-v1:eol+test101+2020",
                "id": "5faae1182f1f5e001b09d32a",
                "anonymous": False,
                "context": "course",
                "title": "asdasd",
                "votes": {},
                "abuse_flaggers": [],
                "read":False,
                "type":"thread",
                "thread_type":"question",
                "at_position_list":[],
                "endorsed":True,
                "last_activity_at":"2020-11-23T15:44:49Z",
                "body":"asdasd"
            }]
        data_all_thread = {"page": 1, "num_pages": 1, "collection": collection}
        data_thread_1 = {}
        get.side_effect = [
            namedtuple(
                "Request", [
                    "status_code", "json"])(
                200, lambda:data_all_thread),
            namedtuple(
                "Request", [
                    "status_code", "text"])(
                400, data_thread_1),
        ]

        request = TestRequest()
        request.method = 'POST'
        data = json.dumps({})
        request.body = data.encode()

        self.xblock.xmodule_runtime.user_is_staff = True
        self.xblock.scope_ids.user_id = self.staff_user.id
        self.xblock.id_forum = 'adsadad'
        response = self.xblock.get_data_forum(request)
        data_response = json.loads(response._app_iter[0].decode())

        self.assertEqual(data_response['result'], 'success')
        lista_alumnos = [{'id': self.staff_user.id,
                          'username': self.staff_user.username,
                          'correo': self.staff_user.email,
                          'score': '',
                          'feedback': '',
                          'student_forum': {"5faae1182f1f5e001b09d32a": {},
                                            }},
                         {'id': self.student.id,
                          'username': self.student.username,
                          'correo': self.student.email,
                          'score': '',
                          'feedback': '',
                          'student_forum': {}}]
        self.assertEqual(data_response['lista_alumnos'], lista_alumnos)

    def test_student_view_render(self):
        """
            Check if xblock student template loads correctly
        """
        self.xblock.scope_ids.user_id = self.student.id
        student_view = self.xblock.student_view()
        student_view_html = student_view.content
        self.assertIn('class="eolgradediscussion_block"', student_view_html)

    @patch('openedx.core.djangoapps.theming.helpers.get_current_request')
    def test_studio_view_render(self,_):
        """
            Check if xblock studio template loads correctly
        """
        studio_view = self.xblock.studio_view()
        studio_view_html = studio_view.content
        self.assertIn('id="eolgradediscussion_loading"', studio_view_html)

    def test_author_view_render(self):
        """
            Check if xblock author template loads correctly
        """
        author_view = self.xblock.author_view()
        author_view_html = author_view.content
        self.assertIn('class="eolgradediscussion_block_author"', author_view_html)

    def test_workbench_scenarios(self):
        """
            Checks that 'workbench_scenarios' methods returns the expected title and XML 
            for the basic EolGradeDiscussionXBlock scenario.
        """
        result_title = 'EolGradeDiscussionXBlock'
        basic_scenario = "<eolgradediscussion/>"
        test_result = self.xblock.workbench_scenarios()
        self.assertEqual(result_title, test_result[0][0])
        self.assertIn(basic_scenario, test_result[0][1])

    def test_get_student_item_dict_student_id_none(self):
        """
            Checks get_student_item_dict fuction when student_id is None
        """
        response = self.xblock.get_student_item_dict(None)
        self.assertEqual(
            response['student_id']._mock_name,
            'anonymous_student_id'
        )
