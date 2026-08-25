# Python Standard Libraries
import json
import logging

# Installed packages (via pip)
from django.conf import settings as DJANGO_SETTINGS
from django.template import Context, Template
from django.urls import reverse
import pkg_resources
import six

# Edx dependencies
from xblock.core import XBlock
from xblock.fields import Integer, Scope, String
from xblock.fragment import Fragment
from xblockutils.resources import ResourceLoader
from xblockutils.studio_editable import StudioEditableXBlockMixin


log = logging.getLogger(__name__)
loader = ResourceLoader(__name__)
# Make '_' a no-op so we can scrape strings


def _(text): return text


XBLOCK_TYPE = "eolgradediscussion"


def reify(meth):
    """
    Decorator which caches value so it is only computed once.
    Keyword arguments:
    inst
    """
    def getter(inst):
        """
        Set value to meth name in dict and returns value.
        """
        value = meth(inst)
        inst.__dict__[meth.__name__] = value
        return value
    return property(getter)


class EolGradeDiscussionXBlock(StudioEditableXBlockMixin, XBlock):

    display_name = String(
        display_name="Display Name",
        help="Display name for this module",
        default="Participación Foro",
        scope=Scope.settings,
    )
    puntajemax = Integer(
        display_name='Puntaje Máximo',
        help='Entero que representa puntaje máximo',
        default=100,
        values={'min': 0},
        scope=Scope.settings,
    )
    id_forum = String(
        display_name=_("Id Forum"),
        help=_("Id forum for this module"),
        default="",
        scope=Scope.settings,
    )
    forum_display_name = String(
        display_name=_("Display Name Forum"),
        help=_("displayname forum for this module"),
        default="",
        scope=Scope.settings,
    )
    has_author_view = True
    has_score = True

    def resource_string(self, path):
        """Handy helper for getting resources from our kit."""
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")

    def author_view(self, context=None):
        context = {'xblock': self, 'location': str(
            self.location).split('@')[-1]}
        template = self.render_template(
            'static/html/author_view.html', context)
        frag = Fragment(template)
        frag.add_css(self.resource_string("static/css/eolgradediscussion.css"))
        return frag

    def studio_view(self, context=None):
        from openedx.core.djangoapps.site_configuration.models import SiteConfiguration
        lms_base = SiteConfiguration.get_value_for_org(
            self.location.org,
            "LMS_BASE",
            DJANGO_SETTINGS.LMS_BASE
        )
        context = {'xblock': self,
                   'location': str(self.location).split('@')[-1]}
        template = self.render_template(
            'static/html/studio_view.html', context)
        frag = Fragment(template)
        frag.add_css(self.resource_string("static/css/eolgradediscussion.css"))
        frag.add_javascript(self.resource_string(
            "static/js/src/eolgradediscussion_studio.js"))
        from openedx.core.djangoapps.theming.helpers import get_current_request
        myrequest = get_current_request()
        absolute_uri = myrequest.build_absolute_uri()
        http_aux = 'https://'
        if 'http://' in absolute_uri:
            http_aux = 'http://'
        settings = {
            'id_forum': self.id_forum,
            'url_get_discussions': '{}{}/api/discussion/v1/course_topics/{}'.format(http_aux, lms_base, str(self.course_id))
            }
        frag.initialize_js('EolGradeDiscussionXBlock', json_args=settings)
        return frag

    def student_view(self, context=None):
        context = self.get_context()
        template = self.render_template(
            'static/html/eolgradediscussion.html', context)
        frag = Fragment(template)
        frag.add_css(self.resource_string("static/css/eolgradediscussion.css"))
        frag.add_javascript(self.resource_string(
            "static/js/src/eolgradediscussion.js"))
        settings = {
            'puntajemax': str(self.puntajemax),
            'location': str(self.location).split('@')[-1]
        }
        frag.initialize_js('EolGradeDiscussionXBlock', json_args=settings)
        return frag

    def get_context(self):
        context = {'xblock': self, 'location': str(
            self.location).split('@')[-1]}
        course_key = self.course_id
        if self.show_staff_grading_interface():
            from django.contrib.auth.models import User
            from submissions import api as submissions_api
            enrolled_students = User.objects.filter(
                courseenrollment__course_id=course_key,
                courseenrollment__is_active=1
            ).order_by('username').values('id', 'username', 'email')
            filter_all_sub = {}
            all_submission = list(
                submissions_api.get_all_course_submission_information(
                    self.course_id, XBLOCK_TYPE))
            for student_item, submission, score in all_submission:
                if self.block_id == student_item['item_id']:
                    filter_all_sub[student_item['student_id']
                                   ] = score['points_earned']
            calificado = 0
            for a in enrolled_students:
                anonymous_id = self.get_anonymous_id(a['id'])
                if anonymous_id in filter_all_sub:
                    if filter_all_sub[anonymous_id] is not None and filter_all_sub[anonymous_id] >= 0:
                        calificado = calificado + 1
            context['calificado'] = calificado
            context['total_student'] = len(enrolled_students)
            context['category'] = type(self).__name__
            context['is_course_staff'] = True
        else:
            score = ''
            feedback = ''
            aux_pun = self.get_score(self.scope_ids.user_id)
            if aux_pun is not None and aux_pun >= 0:
                score = aux_pun
            state = self.get_feedback(self.scope_ids.user_id, course_key, self.block_id)
            if 'feedback' in state:
                feedback = state['feedback']
            context['puntaje'] = score
            context['feedback'] = feedback
            context['is_course_staff'] = False
        return context

    @reify
    def block_course_id(self):
        """
        Return the course_id of the block.
        """
        return six.text_type(self.course_id)

    @reify
    def block_id(self):
        """
        Return the usage_id of the block.
        """
        return six.text_type(self.scope_ids.usage_id)

    def is_course_staff(self):
        # pylint: disable=no-member
        """
         Check if user is course staff.
        """
        return getattr(self.xmodule_runtime, 'user_is_staff', False)

    def get_anonymous_id(self, student_id=None):
        """
            Return anonymous id
        """
        from django.contrib.auth.models import User
        from common.djangoapps.student.models import anonymous_id_for_user

        course_key = self.course_id
        return anonymous_id_for_user(
            User.objects.get(
                id=student_id), course_key)

    def show_staff_grading_interface(self):
        """
        Return if current user is staff and not in studio.
        """
        in_studio_preview = self.scope_ids.user_id is None
        return self.is_course_staff() and not in_studio_preview

    def get_submission(self, student_id=None):
        """
        Get student's most recent submission.
        """
        from submissions import api as submissions_api
        submissions = submissions_api.get_submissions(
            self.get_student_item_dict(student_id)
        )
        if submissions:
            # If I understand docs correctly, most recent submission should
            # be first
            return submissions[0]

    def get_student_item_dict(self, student_id=None):
        # pylint: disable=no-member
        """
        Returns dict required by the submissions app for creating and
        retrieving submissions for a particular student.
        """
        if student_id is None:
            student_id = self.xmodule_runtime.anonymous_student_id
            assert student_id != (
                'MOCK', "Forgot to call 'personalize' in test."
            )
        return {
            "student_id": student_id,
            "course_id": self.block_course_id,
            "item_id": self.block_id,
            "item_type": XBLOCK_TYPE,
        }

    def get_score(self, student_id=None):
        """
        Return student's current score.
        """
        from submissions import api as submissions_api
        anonymous_user_id = self.get_anonymous_id(student_id)
        score = submissions_api.get_score(
            self.get_student_item_dict(anonymous_user_id)
        )
        if score:
            return score['points_earned']
        else:
            return None

    def get_all_thread(self, discussion_id):
        """
            Get all thread with the specified discussion ID.
        """
        import openedx.core.djangoapps.django_comment_common.comment_client as cc
        from openedx.core.djangoapps.django_comment_common.utils import ThreadContext
        query_params = {
            'page': 1,
            'per_page': DJANGO_SETTINGS.EOLGRADEDISCUSSION_LIMIT_THREAD,
            'sort_key': 'activity',
            'course_id': six.text_type(self.course_id),
            'context': ThreadContext.COURSE,
            'commentable_id': discussion_id
        }
        try:
            paginated_results = cc.Thread.search(query_params)
        except cc.utils.CommentClientRequestError:
            log.info(
                'EolGradeForum - Error en obtener las publicaciones id_forum: {}'.format(discussion_id))
            return None
        return {
            'collection': paginated_results.collection,
            'page': paginated_results.page,
            'num_pages': paginated_results.num_pages}

    def find_thread(self, thread_id, resp_init, resp_limit):
        """
         sort_key_mapper = {
            "date" => :created_at,
            "activity" => :last_activity_at,
            "votes" => :"votes.point",
            "comments" => :comment_count,
            }
        Finds the discussion thread with the specified ID.
        """
        import openedx.core.djangoapps.django_comment_common.comment_client as cc
        try:
            thread = cc.Thread.find(thread_id).retrieve(
                with_responses=True,
                recursive=True,
                response_skip=resp_init,
                response_limit=resp_limit)
        except cc.utils.CommentClientRequestError:
            log.info(
                'EolGradeForum - Error en obtener la publicacion thread_id: {}'.format(thread_id))
            return None

        return thread

    def validar_datos_all(self, data):
        """
            Verify if all students data is valid
        """
        score = True
        for fila in data.get('data'):
            if fila['score'] != '':
                if not str(fila['score']).lstrip(
                        '+').isdigit() or int(fila['score']) < 0 or int(fila['score']) > self.puntajemax:
                    score = False
                    break
        return score

    def get_feedback(self, student_id, course_key, block_key):
        """
        Return feedback by student_id
        """
        from lms.djangoapps.courseware.models import StudentModule
        try:
            student_module = StudentModule.objects.get(
                student_id=student_id,
                course_id=self.course_id,
                module_state_key=self.location
            )
        except StudentModule.DoesNotExist:
            student_module = None

        if student_module:
            return json.loads(student_module.state)
        return {}

    def get_all_student_module(self, course_key, block_key):
        """
        Return all feedback
        """
        from lms.djangoapps.courseware.models import StudentModule
        try:
            student_modules = StudentModule.objects.filter(
                course_id=self.course_id,
                module_state_key=self.location
            )
        except StudentModule.DoesNotExist:
            student_modules = None

        if student_modules:
            all_modules = {}
            for module in student_modules:
                all_modules[module.student_id] = json.loads(module.state)
            return all_modules
        return {}

    def get_or_create_student_module(self, student_id):
        """
        Gets or creates a StudentModule for the given user for this block
        Returns:
            StudentModule: A StudentModule object
        """
        # pylint: disable=no-member
        from lms.djangoapps.courseware.models import StudentModule
        student_module, created = StudentModule.objects.get_or_create(
            course_id=self.course_id,
            module_state_key=self.location,
            student_id=student_id,
            defaults={
                'state': '{}',
                'module_type': self.category,
            }
        )
        if created:
            log.info(
                "Created student module %s [course: %s] [student: %s]",
                student_module.module_state_key,
                student_module.course_id,
                student_module.student.username
            )
        return student_module

    @XBlock.json_handler
    def savestudentanswersall(self, data, suffix=''):
        """
            Save the score of all students
        """
        valida = self.validar_datos_all(data)
        calificado = 0
        if self.show_staff_grading_interface() and valida:
            for user_data in data.get('data'):
                student_module = self.get_or_create_student_module(user_data['user_id'])
                state = json.loads(student_module.state)
                state['feedback'] = user_data['feedback']
                student_module.state = json.dumps(state)
                student_module.save()
                if user_data['score'] != '':
                    score = int(user_data['score'])
                    from common.djangoapps.student.models import anonymous_id_for_user
                    from django.contrib.auth.models import User
                    from submissions import api as submissions_api
                    course_key = self.course_id
                    user_score = User.objects.get(id=user_data['user_id'])
                    anonymous_user_id = anonymous_id_for_user(
                        user_score, course_key)
                    submission = self.get_submission(anonymous_user_id)

                    if submission:
                        submissions_api.set_score(
                            submission['uuid'], score, self.puntajemax)
                    else:
                        calificado = calificado + 1
                        student_item = {
                            'student_id': anonymous_user_id,
                            'course_id': self.block_course_id,
                            'item_id': self.block_id,
                            'item_type': XBLOCK_TYPE
                        }
                        submission = submissions_api.create_submission(
                            student_item, 'any answer')
                        submissions_api.set_score(
                            submission['uuid'], score, self.puntajemax)

            return {
                'result': 'success',
                'calificado': calificado}

        return {'result': 'error'}

    @XBlock.json_handler
    def studio_submit(self, data, suffix=''):
        """
        Called when submitting the form in Studio.
        """
        if data.get('puntajemax').lstrip(
                '+').isdigit() and int(data.get('puntajemax')) >= 0:
            self.display_name = data.get('display_name') or ""
            self.id_forum = data.get('id_forum') or ""
            self.forum_display_name = data.get('forum_display_name') or ""
            self.puntajemax = int(data.get('puntajemax')) or 100
            return {'result': 'success'}
        return {'result': 'error'}

    @XBlock.json_handler
    def get_data_forum(self, request, suffix=''):
        """
            Get all threads with comments
        """
        if not self.show_staff_grading_interface():
            log.info('EolGradeForum - Usuario sin Permisos - user_id: {}'.format(self.scope_ids.user_id))
            return { 'result': 'user is not course staff'}
        from django.contrib.auth.models import User
        from submissions import api as submissions_api
        course_key = self.course_id
        if self.id_forum == '':
            log.info('EolGradeForum - Componente no configurado - id_forum == ""')
            return {'result': 'no id_forum'}
        hilos = self.get_all_thread(self.id_forum)
        if hilos is None:
            return {'result': 'error'}
        if len(hilos['collection']) == 0:
            log.info('EolGradeForum - Foro sin publicaciones')
            return {'result': 'no data'}
        content_forum, student_data = self.reduce_data_forum(
            hilos['collection'])
        enrolled_students = User.objects.filter(
            courseenrollment__course_id=course_key,
            courseenrollment__is_active=1
        ).order_by('username').values('id', 'username', 'email')
        filter_all_sub = {}
        all_submission = list(
            submissions_api.get_all_course_submission_information(
                self.course_id, XBLOCK_TYPE))
        for student_item, submission, score in all_submission:
            if self.block_id == student_item['item_id']:
                filter_all_sub[student_item['student_id']
                               ] = score['points_earned']

        lista_alumnos = []
        calificado = 0
        states = self.get_all_student_module(course_key, self.block_id)
        for a in enrolled_students:
            student_forum = {}
            if str(a['id']) in student_data:
                student_forum = student_data[str(a['id'])]
            puntaje = ''
            anonymous_id = self.get_anonymous_id(a['id'])
            if anonymous_id in filter_all_sub:
                if filter_all_sub[anonymous_id] is not None and filter_all_sub[anonymous_id] >= 0:
                    puntaje = filter_all_sub[anonymous_id]
                    calificado = calificado + 1
            feedback = ''
            if a['id'] in states:
                if 'feedback' in states[a['id']]:
                    state = states[a['id']]
                    feedback = state['feedback']
            lista_alumnos.append({'id': a['id'],
                                  'username': a['username'],
                                  'correo': a['email'],
                                  'score': puntaje,
                                  'feedback': feedback,
                                  'student_forum': student_forum})

        return {
            'result': 'success',
            'lista_alumnos': lista_alumnos,
            'content_forum': content_forum}

    def reduce_data_forum(self, hilos):
        """
            Get comments for each thread
        """
        content_forum = {}
        student_data = {}
        for hilo in hilos:
            aux_thread = {
                'id': hilo['id'],
                'user_id': hilo['user_id'],
                'username': hilo['username'],
                'anonymous': hilo['anonymous'],
                'thread_type': hilo['thread_type'],
                'type': hilo['type'],
                'endorsed': hilo['endorsed'],
                'title': hilo['title'],
                'body': hilo['body'],
                'comments_count': hilo['comments_count'],
                'children': [],
                'url_thread': reverse('single_thread', kwargs={'course_id':hilo['course_id'],'discussion_id':hilo['commentable_id'], 'thread_id':hilo['id']})
            }
            lista_comentarios, resp_total = self.get_all_comments_thread(hilo['id'])
            aux_thread['resp_total'] = resp_total

            for comment in lista_comentarios:
                aux_thread['children'].append(comment['id'])
                aux_comment = {
                    'id': comment['id'],
                    'username': comment['username'],
                    'user_id': comment['user_id'],
                    'body': comment['body'],
                    'parent_id': comment['thread_id'],
                    'type': comment['type'],
                    'children': [],
                    'endorsed': comment['endorsed']
                }
                for sub_comment in comment['children']:
                    aux_comment['children'].append(sub_comment['id'])
                    aux_sub_comment = {
                        'id': sub_comment['id'],
                        'username': sub_comment['username'],
                        'user_id': sub_comment['user_id'],
                        'body': sub_comment['body'],
                        'parent_id': sub_comment['thread_id'],
                        'type': sub_comment['type'],
                        'children': [],
                        'endorsed': sub_comment['endorsed']
                    }
                    content_forum[sub_comment['id']] = aux_sub_comment
                    if hilo['user_id'] != sub_comment['user_id'] and comment['user_id'] != sub_comment['user_id']:
                        if sub_comment['user_id'] not in student_data:
                            student_data[sub_comment['user_id']] = {}
                        if hilo['id'] not in student_data[sub_comment['user_id']]:
                            student_data[sub_comment['user_id']
                                         ][hilo['id']] = {}
                        if comment['id'] not in student_data[sub_comment['user_id']][hilo['id']]:
                            student_data[sub_comment['user_id']
                                         ][hilo['id']][comment['id']] = []

                        student_data[sub_comment['user_id']][hilo['id']
                                                             ][comment['id']].append(sub_comment['id'])
                ##END FOR###############################################
                content_forum[comment['id']] = aux_comment
                if hilo['user_id'] != comment['user_id']:
                    if comment['user_id'] not in student_data:
                        student_data[comment['user_id']] = {}
                    if hilo['id'] not in student_data[comment['user_id']]:
                        student_data[comment['user_id']][hilo['id']] = {}
                    student_data[comment['user_id']
                                 ][hilo['id']][comment['id']] = []

            ##END FOR###################################################
            content_forum[hilo['id']] = aux_thread
            if hilo['user_id'] not in student_data:
                student_data[hilo['user_id']] = {}
            student_data[hilo['user_id']][hilo['id']] = {}

        return content_forum, student_data

    def get_all_comments_thread(self, id_thread):
        """
            Get all comments for id_thread
        """
        children = []
        endorsed_responses = []
        non_endorsed_responses = []
        limit = 200
        skip = 0
        aux = -1
        resp_total = 0

        while aux < resp_total:
            resp_hilo = self.find_thread(id_thread, skip, limit)
            if resp_hilo is not None:
                thread = resp_hilo.attributes
                resp_total = thread['resp_total']
                if thread['thread_type'] == 'discussion':
                    children.extend(thread['children'])
                elif thread['thread_type'] == 'question':
                    endorsed_responses.extend(thread['endorsed_responses'])
                    non_endorsed_responses.extend(thread['non_endorsed_responses'])
            aux = limit
            skip = limit
            limit = limit + 200

        list_comment = children + endorsed_responses + non_endorsed_responses
        return list_comment, resp_total

    def render_template(self, template_path, context):
        template_str = self.resource_string(template_path)
        template = Template(template_str)
        return template.render(Context(context))

        # workbench while developing your XBlock.
    @staticmethod
    def workbench_scenarios():
        """A canned scenario for display in the workbench."""
        return [
            ("EolGradeDiscussionXBlock",
             """<eolgradediscussion/>
             """),
            ("Multiple EolGradeDiscussionXBlock",
             """<vertical_demo>
                <eolgradediscussion/>
                <eolgradediscussion/>
                <eolgradediscussion/>
                </vertical_demo>
             """),
        ]
