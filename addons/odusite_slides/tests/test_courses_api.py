"""Tests for the odusite_slides API (see specs/modules/odusite_slides.md).

Covers the catalog visibility rules (is_visible search: 'connected'/'members'
channels are hidden from anonymous users, not merely locked), the content lock
rule (preview OR public-visibility channel OR member), join (public vs
invite-only), completion tracking and the quiz flow (correctness hidden until
completed, stock reward computation).
"""

from odoo.tests.common import tagged

from odoo.addons.odusite_base.tests.common import OdusiteHttpCase


@tagged('post_install', '-at_install')
class TestCoursesApi(OdusiteHttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Channel = cls.env['slide.channel']
        Slide = cls.env['slide.slide']

        cls.channel_public = Channel.create({
            'name': 'Odusite Public Course',
            'visibility': 'public',
            'enroll': 'public',
            'is_published': True,
            'description_short': '<p>Learn Odusite basics</p>',
            'description_html': '<p>The full Odusite course description</p>',
        })
        cls.slide_preview = Slide.create({
            'name': 'Odusite Intro Preview',
            'channel_id': cls.channel_public.id,
            'slide_category': 'article',
            'html_content': '<p>Preview article body</p>',
            'is_preview': True,
            'is_published': True,
            'completion_time': 0.5,
            'sequence': 1,
        })
        cls.slide_full = Slide.create({
            'name': 'Odusite Full Article',
            'channel_id': cls.channel_public.id,
            'slide_category': 'article',
            'html_content': '<p>Members article body</p>',
            'is_preview': False,
            'is_published': True,
            'completion_time': 1.0,
            'sequence': 2,
        })
        # quiz questions need at least one correct and one incorrect answer
        cls.slide_quiz = Slide.create({
            'name': 'Odusite Quiz',
            'channel_id': cls.channel_public.id,
            'slide_category': 'quiz',
            'is_published': True,
            'sequence': 3,
            'question_ids': [
                (0, 0, {
                    'question': 'What is Odusite?',
                    'sequence': 1,
                    'answer_ids': [
                        (0, 0, {'text_value': 'A headless CMS setup',
                                'is_correct': True, 'sequence': 1}),
                        (0, 0, {'text_value': 'A coffee brand', 'sequence': 2}),
                    ],
                }),
                (0, 0, {
                    'question': 'Which header authenticates the site?',
                    'sequence': 2,
                    'answer_ids': [
                        (0, 0, {'text_value': 'X-Odusite-Token',
                                'is_correct': True, 'sequence': 1}),
                        (0, 0, {'text_value': 'X-Forwarded-For', 'sequence': 2}),
                    ],
                }),
            ],
        })

        # visible to signed-in users only; non-members see locked content
        cls.channel_connected = Channel.create({
            'name': 'Odusite Connected Course',
            'visibility': 'connected',
            'enroll': 'public',
            'is_published': True,
        })
        cls.conn_preview = Slide.create({
            'name': 'Odusite Connected Preview',
            'channel_id': cls.channel_connected.id,
            'slide_category': 'article',
            'html_content': '<p>Connected preview body</p>',
            'is_preview': True,
            'is_published': True,
            'sequence': 1,
        })
        cls.conn_full = Slide.create({
            'name': 'Odusite Connected Full',
            'channel_id': cls.channel_connected.id,
            'slide_category': 'article',
            'html_content': '<p>Connected members body</p>',
            'is_preview': False,
            'is_published': True,
            'sequence': 2,
        })

        cls.channel_invite = Channel.create({
            'name': 'Odusite Invite Course',
            'visibility': 'public',
            'enroll': 'invite',
            'is_published': True,
        })
        # visibility 'members' forces enroll 'invite' (SQL constraint)
        cls.channel_members = Channel.create({
            'name': 'Odusite Members Course',
            'visibility': 'members',
            'enroll': 'invite',
            'is_published': True,
        })
        cls.channel_unpublished = Channel.create({
            'name': 'Odusite Unpublished Course',
            'visibility': 'public',
            'enroll': 'public',
            'is_published': False,
        })

        cls.student = cls.create_portal_user(
            login='course.student@example.com', name='Course Student')

    # -- helpers -----------------------------------------------------------

    def _slug(self, record):
        return self.env['ir.http']._slug(record)

    def _list_ids(self, path, bearer=None):
        response, body = self.api('GET', path, bearer=bearer)
        self.assertEqual(response.status_code, 200, body)
        return {item['id'] for item in body['data']}

    def _curriculum_slides(self, data):
        return {
            slide['id']: slide
            for group in data['curriculum']
            for slide in group['slides']
        }

    def _join(self, channel, bearer):
        response, body = self.api(
            'POST', f'/courses/{channel.id}/join', bearer=bearer)
        self.assertEqual(response.status_code, 200, body)
        return body['data']

    def _quiz_path(self):
        return (f'/courses/{self.channel_public.id}'
                f'/slides/{self.slide_quiz.id}/quiz')

    def _quiz_answers(self, correct=True):
        return {
            str(question.id): question.answer_ids.filtered(
                lambda a: a.is_correct == correct)[:1].id
            for question in self.slide_quiz.question_ids
        }

    # -- catalog -----------------------------------------------------------

    def test_courses_list_anonymous(self):
        ids = self._list_ids('/courses?search=Odusite&limit=100')
        self.assertIn(self.channel_public.id, ids)
        self.assertIn(self.channel_invite.id, ids)
        # actual behavior: non-public visibility channels are hidden from
        # anonymous users (is_visible search), not "listed but locked"
        self.assertNotIn(self.channel_connected.id, ids)
        self.assertNotIn(self.channel_members.id, ids)
        self.assertNotIn(self.channel_unpublished.id, ids)

        response, body = self.api('GET', '/courses?search=Odusite+Public&limit=100')
        entry = next(c for c in body['data'] if c['id'] == self.channel_public.id)
        self.assertEqual(entry['slug'], self._slug(self.channel_public))
        self.assertEqual(entry['enroll'], 'public')
        self.assertFalse(entry['is_member'])
        self.assertEqual(entry['slide_count'], 3)
        self.assertIn('Learn Odusite basics', entry['description_short'])

    def test_courses_list_jwt(self):
        bearer = self.make_access_token(self.student)
        ids = self._list_ids('/courses?search=Odusite&limit=100', bearer=bearer)
        self.assertIn(self.channel_public.id, ids)
        self.assertIn(self.channel_connected.id, ids)  # signed in
        self.assertIn(self.channel_invite.id, ids)
        self.assertNotIn(self.channel_members.id, ids)  # still not a member
        self.assertNotIn(self.channel_unpublished.id, ids)

    def test_course_detail_public_anonymous(self):
        response, body = self.api(
            'GET', f'/courses/{self._slug(self.channel_public)}')
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertEqual(data['id'], self.channel_public.id)
        self.assertFalse(data['is_member'])
        self.assertIsNone(data['completion'])  # anonymous: no membership
        self.assertIn('full Odusite course description', data['description_html'])
        self.assertTrue(data['seo']['title'])
        self.assertEqual(data['prerequisites'], [])

        slides = self._curriculum_slides(data)
        self.assertEqual(
            set(slides),
            {self.slide_preview.id, self.slide_full.id, self.slide_quiz.id})
        # public-visibility course: nothing is locked, even for anonymous
        self.assertFalse(any(slide['is_locked'] for slide in slides.values()))
        self.assertTrue(slides[self.slide_preview.id]['is_preview'])
        self.assertEqual(slides[self.slide_preview.id]['type'], 'article')
        self.assertEqual(slides[self.slide_quiz.id]['type'], 'quiz')
        self.assertFalse(any(slide['completed'] for slide in slides.values()))

    def test_course_detail_connected_lock_states(self):
        # hidden from anonymous entirely
        response, body = self.api('GET', f'/courses/{self.channel_connected.id}')
        self.assert_api_error(response, body, 404, 'not_found')

        bearer = self.make_access_token(self.student)
        response, body = self.api(
            'GET', f'/courses/{self.channel_connected.id}', bearer=bearer)
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertFalse(data['is_member'])
        self.assertIsNone(data['completion'])
        slides = self._curriculum_slides(data)
        self.assertFalse(slides[self.conn_preview.id]['is_locked'])
        self.assertTrue(slides[self.conn_full.id]['is_locked'])

    def test_course_detail_hidden_channels_404(self):
        bearer = self.make_access_token(self.student)
        for channel in (self.channel_members, self.channel_unpublished):
            response, body = self.api('GET', f'/courses/{channel.id}')
            self.assert_api_error(response, body, 404, 'not_found')
            response, body = self.api(
                'GET', f'/courses/{channel.id}', bearer=bearer)
            self.assert_api_error(response, body, 404, 'not_found')

    # -- slide content -----------------------------------------------------

    def test_slide_content_public_anonymous(self):
        base = f'/courses/{self.channel_public.id}/slides'
        response, body = self.api('GET', f'{base}/{self.slide_preview.id}')
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertEqual(data['type'], 'article')
        self.assertTrue(data['is_preview'])
        self.assertIn('Preview article body', data['html_content'])
        self.assertFalse(data['completed'])
        self.assertEqual(data['user_vote'], 0)

        # public-visibility course: non-preview content is open too
        response, body = self.api('GET', f'{base}/{self.slide_full.id}')
        self.assertEqual(response.status_code, 200, body)
        self.assertIn('Members article body', body['data']['html_content'])

    def test_slide_content_connected_locked(self):
        base = f'/courses/{self.channel_connected.id}/slides'
        # anonymous cannot even resolve the channel
        response, body = self.api('GET', f'{base}/{self.conn_preview.id}')
        self.assert_api_error(response, body, 404, 'not_found')

        bearer = self.make_access_token(self.student)
        response, body = self.api(
            'GET', f'{base}/{self.conn_preview.id}', bearer=bearer)
        self.assertEqual(response.status_code, 200, body)
        self.assertIn('Connected preview body', body['data']['html_content'])

        response, body = self.api(
            'GET', f'{base}/{self.conn_full.id}', bearer=bearer)
        self.assert_api_error(response, body, 403, 'members_only')

    # -- membership & completion -------------------------------------------

    def test_join_and_complete_flow(self):
        bearer = self.make_access_token(self.student)
        data = self._join(self.channel_connected, bearer)
        self.assertEqual(
            data, {'joined': True, 'is_member': True, 'completion': 0})

        base = f'/courses/{self.channel_connected.id}/slides'
        # unlocked after joining
        response, body = self.api(
            'GET', f'{base}/{self.conn_full.id}', bearer=bearer)
        self.assertEqual(response.status_code, 200, body)
        self.assertIn('Connected members body', body['data']['html_content'])

        response, body = self.api(
            'POST', f'{base}/{self.conn_full.id}/complete', bearer=bearer)
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(body['data'], {'completed': True, 'completion': 50})

        response, body = self.api(
            'GET', f'/courses/{self.channel_connected.id}', bearer=bearer)
        data = body['data']
        self.assertTrue(data['is_member'])
        self.assertEqual(data['completion'], 50)
        slides = self._curriculum_slides(data)
        self.assertTrue(slides[self.conn_full.id]['completed'])
        self.assertFalse(slides[self.conn_full.id]['is_locked'])
        self.assertFalse(slides[self.conn_preview.id]['completed'])

    def test_complete_requires_membership(self):
        bearer = self.make_access_token(self.student)
        response, body = self.api(
            'POST',
            f'/courses/{self.channel_connected.id}/slides/{self.conn_full.id}/complete',
            bearer=bearer)
        self.assert_api_error(response, body, 403, 'members_only')

    def test_complete_requires_jwt(self):
        response, body = self.api(
            'POST',
            f'/courses/{self.channel_public.id}/slides/{self.slide_full.id}/complete')
        self.assert_api_error(response, body, 401, 'unauthorized')

    def test_join_invite_only(self):
        bearer = self.make_access_token(self.student)
        response, body = self.api(
            'POST', f'/courses/{self.channel_invite.id}/join', bearer=bearer)
        self.assert_api_error(response, body, 403, 'invite_only')
        self.assertFalse(self.env['slide.channel.partner'].search([
            ('channel_id', '=', self.channel_invite.id),
            ('partner_id', '=', self.student.partner_id.id),
        ]))

    # -- quiz ---------------------------------------------------------------

    def test_quiz_get_anonymous(self):
        response, body = self.api('GET', self._quiz_path())
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertFalse(data['completed'])
        self.assertEqual(data['karma_max'], self.slide_quiz.quiz_first_attempt_reward)
        self.assertEqual(len(data['questions']), 2)
        for question in data['questions']:
            self.assertTrue(question['question'])
            self.assertEqual(len(question['answers']), 2)
            # correctness must not leak before the quiz is completed
            for answer in question['answers']:
                self.assertIsNone(answer['is_correct'])

    def test_quiz_submit_wrong(self):
        bearer = self.make_access_token(self.student)
        self._join(self.channel_public, bearer)
        response, body = self.api(
            'POST', self._quiz_path(),
            {'answers': self._quiz_answers(correct=False)}, bearer=bearer)
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertFalse(data['completed'])
        self.assertEqual(data['karma_won'], 0)
        self.assertEqual(data['attempts_count'], 1)
        self.assertEqual(data['completion'], 0)
        self.assertFalse(
            any(answer['is_correct'] for answer in data['answers'].values()))

    def test_quiz_submit_correct(self):
        bearer = self.make_access_token(self.student)
        self._join(self.channel_public, bearer)
        response, body = self.api(
            'POST', self._quiz_path(),
            {'answers': self._quiz_answers(correct=True)}, bearer=bearer)
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertTrue(data['completed'])
        self.assertEqual(data['attempts_count'], 1)
        self.assertEqual(
            data['karma_won'], self.slide_quiz.quiz_first_attempt_reward)
        self.assertGreater(data['completion'], 0)  # 1 of 3 slides done
        self.assertTrue(
            all(answer['is_correct'] for answer in data['answers'].values()))

        # correctness is revealed once the quiz is completed
        response, body = self.api('GET', self._quiz_path(), bearer=bearer)
        self.assertEqual(response.status_code, 200, body)
        self.assertTrue(body['data']['completed'])
        flags = [
            answer['is_correct']
            for question in body['data']['questions']
            for answer in question['answers']
        ]
        self.assertIn(True, flags)
        self.assertIn(False, flags)

        # resubmitting a completed quiz is rejected
        response, body = self.api(
            'POST', self._quiz_path(),
            {'answers': self._quiz_answers(correct=True)}, bearer=bearer)
        self.assert_api_error(response, body, 409, 'quiz_done')

    def test_quiz_submit_incomplete(self):
        bearer = self.make_access_token(self.student)
        self._join(self.channel_public, bearer)
        question = self.slide_quiz.question_ids.sorted('sequence')[0]
        answers = {
            str(question.id): question.answer_ids.filtered('is_correct')[:1].id}
        response, body = self.api(
            'POST', self._quiz_path(), {'answers': answers}, bearer=bearer)
        self.assert_api_error(response, body, 422, 'quiz_incomplete')

    def test_quiz_submit_requires_membership(self):
        bearer = self.make_access_token(self.student)
        response, body = self.api(
            'POST', self._quiz_path(),
            {'answers': self._quiz_answers(correct=True)}, bearer=bearer)
        self.assert_api_error(response, body, 403, 'members_only')

    def test_complete_quiz_slide_rejected(self):
        # quiz slides are completed by submitting the quiz, not /complete
        bearer = self.make_access_token(self.student)
        self._join(self.channel_public, bearer)
        response, body = self.api(
            'POST',
            f'/courses/{self.channel_public.id}/slides/{self.slide_quiz.id}/complete',
            bearer=bearer)
        self.assert_api_error(response, body, 422, 'validation_error')
