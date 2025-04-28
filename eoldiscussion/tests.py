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
        self.assertEqual(data['error'], 'Error con los parámetros.')

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
        self.assertEqual(data['error'], 'El limite de caracteres debe ser un entero.')

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
        self.assertEqual(data['error'], 'Falta definir las fechas del foro.')

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
        self.assertEqual(data['error'], 'Error con los formatos en las fechas del foro.')

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
            'start_date':'2025-04-28T14:30',
            'end_date':'2025-03-28T14:30',
        })

        request.body = data.encode()
        response = self.xblock.submit_studio_edits(request)
        data = json.loads(response._app_iter[0].decode())
        self.assertEqual(data['error'], 'La fecha de cierre debe ser mayor a la fecha de inicio del foro.')

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
            'start_date':'2025-03-28T14:30',
            'end_date':'2025-04-28T14:30',
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
        self.xblock.start_date = '2024-12-01T08:00:00'
        self.xblock.end_date = '2024-12-01T17:00:00'
        student_view = self.xblock.student_view()
        student_view_html = student_view.content
        self.assertIn('Contenido Studio', student_view_html)

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

