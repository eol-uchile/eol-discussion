# -*- coding: utf-8 -*-
# Python Standard Libraries
from collections import namedtuple
import json
import logging

# Installed packages (via pip)
from mock import patch, Mock

# Edx dependencies
from common.djangoapps.student.roles import CourseStaffRole
from common.djangoapps.student.tests.factories import UserFactory, CourseEnrollmentFactory
from common.djangoapps.util.testing import UrlResetMixin
from xblock.field_data import DictFieldData
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

# Internal project dependencies
from .eolgradediscussion import EolGradeDiscussionXBlock

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
