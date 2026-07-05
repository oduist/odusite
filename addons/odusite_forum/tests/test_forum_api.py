"""Tests for the odusite_forum API (see specs/modules/odusite_forum.md).

Covers public reads (forums, question list filters, detail, tags, profiles),
JWT actions (ask, answer, accept, vote, comment) and the documented error
mapping: stock karma AccessErrors -> 403 `karma_required` with
``details.required``, own-post voting -> 422 `own_post`.
"""

from odoo.tests.common import tagged

from odoo.addons.odusite_base.tests.common import OdusiteHttpCase


@tagged('post_install', '-at_install')
class TestForumApi(OdusiteHttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # anonymous profile reads: the viewer (public user, karma 0) must pass
        # the website_profile karma_profile_min gate (default 150)
        cls.website.karma_profile_min = 0

        cls.forum = cls.env['forum.forum'].create({
            'name': 'Odusite Help Forum',
            'description': 'Questions about Odusite',
        })

        cls.user_asker = cls.create_portal_user(
            login='forum.asker@example.com', name='Forum Asker')
        cls.user_voter = cls.create_portal_user(
            login='forum.voter@example.com', name='Forum Voter')
        cls.user_newbie = cls.create_portal_user(
            login='forum.newbie@example.com', name='Forum Newbie')
        # enough karma for ask (3) / answer (3) / upvote (5) / accept own (20)
        # and above karma_post (100) so questions skip the moderation queue
        (cls.user_asker + cls.user_voter).karma = 1000
        cls.user_newbie.karma = 0
        # profiles of other users are only exposed when website_published
        cls.user_asker.website_published = True

        Post = cls.env['forum.post']
        cls.question = Post.with_user(cls.user_asker).create({
            'forum_id': cls.forum.id,
            'name': 'Odusite fixture question',
            'content': '<p>How do I test the Odusite forum API?</p>',
        })
        cls.answer = Post.with_user(cls.user_voter).create({
            'forum_id': cls.forum.id,
            'name': 'Re: Odusite fixture question',
            'content': '<p>With OdusiteHttpCase, of course.</p>',
            'parent_id': cls.question.id,
        })

    # -- helpers -----------------------------------------------------------

    def _slug(self, record):
        return self.env['ir.http']._slug(record)

    def _list_ids(self, path, bearer=None):
        response, body = self.api('GET', path, bearer=bearer)
        self.assertEqual(response.status_code, 200, body)
        return {item['id'] for item in body['data']}

    def _ask(self, user, name):
        """ORM shortcut for per-test question fixtures."""
        return self.env['forum.post'].with_user(user).create({
            'forum_id': self.forum.id,
            'name': name,
            'content': f'<p>{name}</p>',
        })

    # -- public reads ------------------------------------------------------

    def test_forums_list(self):
        response, body = self.api('GET', '/forum/forums')
        self.assertEqual(response.status_code, 200, body)
        forum = next(f for f in body['data'] if f['id'] == self.forum.id)
        self.assertEqual(forum['name'], 'Odusite Help Forum')
        self.assertEqual(forum['slug'], self._slug(self.forum))
        self.assertEqual(forum['description'], 'Questions about Odusite')
        self.assertEqual(forum['mode'], self.forum.mode)
        self.assertGreaterEqual(forum['post_count'], 1)

    def test_question_detail(self):
        response, body = self.api('GET', f'/forum/posts/{self._slug(self.question)}')
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertEqual(data['id'], self.question.id)
        self.assertEqual(data['name'], 'Odusite fixture question')
        self.assertIn('How do I test', data['content_html'])
        self.assertEqual(data['forum']['id'], self.forum.id)
        self.assertEqual(data['votes'], 0)
        self.assertEqual(data['answer_count'], 1)
        self.assertFalse(data['has_validated_answer'])
        self.assertEqual(data['author']['name'], 'Forum Asker')
        # anonymous request: no user_context block
        self.assertNotIn('user_context', data)
        self.assertEqual(len(data['answers']), 1)
        answer = data['answers'][0]
        self.assertEqual(answer['id'], self.answer.id)
        self.assertIn('OdusiteHttpCase', answer['content_html'])
        self.assertFalse(answer['is_correct'])
        self.assertEqual(answer['author']['name'], 'Forum Voter')

    def test_question_detail_user_context(self):
        bearer = self.make_access_token(self.user_asker)
        response, body = self.api(
            'GET', f'/forum/posts/{self.question.id}', bearer=bearer)
        self.assertEqual(response.status_code, 200, body)
        context = body['data']['user_context']
        self.assertTrue(context['can_edit'])  # own post, karma_edit_own = 1
        self.assertTrue(context['can_answer'])
        self.assertTrue(context['can_upvote'])
        self.assertTrue(context['can_accept'])  # question author
        self.assertEqual(context['vote'], 0)
        self.assertFalse(context['is_favourite'])

    # -- ask ---------------------------------------------------------------

    def test_ask_question(self):
        bearer = self.make_access_token(self.user_asker)
        response, body = self.api('POST', '/forum/posts', {
            'forum_id': self.forum.id,
            'name': 'Odusite brand new question',
            'content': '<p>Fresh content for the ask endpoint.</p>',
            'tags': ['odusite-testing'],
        }, bearer=bearer)
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertEqual(data['state'], 'active')  # karma above karma_post
        question = self.env['forum.post'].browse(data['id'])
        self.assertEqual(question.create_uid, self.user_asker)
        self.assertEqual(question.tag_ids.mapped('name'), ['odusite-testing'])

        # the new question is unanswered; the fixture one (answered) is not
        unanswered = self._list_ids(
            f'/forum/posts?forum={self.forum.id}&filter=unanswered&limit=100')
        self.assertIn(data['id'], unanswered)
        self.assertNotIn(self.question.id, unanswered)

        response, body = self.api('GET', f'/forum/tags?forum={self.forum.id}')
        self.assertEqual(response.status_code, 200, body)
        self.assertIn('odusite-testing', [t['name'] for t in body['data']])

    def test_ask_requires_jwt(self):
        response, body = self.api('POST', '/forum/posts', {
            'forum_id': self.forum.id,
            'name': 'Anonymous question',
            'content': '<p>Should be rejected.</p>',
        })
        self.assert_api_error(response, body, 401, 'unauthorized')

    # -- answer / accept ---------------------------------------------------

    def test_answer_and_accept(self):
        question = self._ask(self.user_asker, 'Odusite question to solve')
        bearer_voter = self.make_access_token(self.user_voter)
        bearer_asker = self.make_access_token(self.user_asker)

        response, body = self.api(
            'POST', f'/forum/posts/{question.id}/answers',
            {'content': '<p>The definitive answer.</p>'}, bearer=bearer_voter)
        self.assertEqual(response.status_code, 200, body)
        answer_id = body['data']['id']
        self.assertFalse(body['data']['is_correct'])

        # accept as the question author
        response, body = self.api(
            'POST', f'/forum/posts/{answer_id}/accept', bearer=bearer_asker)
        self.assertEqual(response.status_code, 200, body)
        self.assertTrue(body['data']['is_correct'])

        response, body = self.api('GET', f'/forum/posts/{question.id}')
        self.assertEqual(response.status_code, 200, body)
        self.assertTrue(body['data']['has_validated_answer'])
        self.assertTrue(body['data']['answers'][0]['is_correct'])

        solved = self._list_ids(
            f'/forum/posts?forum={self.forum.id}&filter=solved&limit=100')
        self.assertIn(question.id, solved)
        self.assertNotIn(self.question.id, solved)

    def test_accept_own_answer_rejected(self):
        question = self._ask(self.user_asker, 'Odusite self accept question')
        bearer_voter = self.make_access_token(self.user_voter)
        response, body = self.api(
            'POST', f'/forum/posts/{question.id}/answers',
            {'content': '<p>My own answer.</p>'}, bearer=bearer_voter)
        self.assertEqual(response.status_code, 200, body)
        # the answer author cannot accept their own answer
        response, body = self.api(
            'POST', f"/forum/posts/{body['data']['id']}/accept",
            bearer=bearer_voter)
        self.assert_api_error(response, body, 422, 'own_post')

    # -- votes -------------------------------------------------------------

    def test_vote_and_retract(self):
        bearer = self.make_access_token(self.user_voter)
        response, body = self.api(
            'POST', f'/forum/posts/{self.question.id}/vote',
            {'vote': 1}, bearer=bearer)
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(body['data'], {'votes': 1, 'user_vote': 1})

        response, body = self.api(
            'GET', f'/forum/posts/{self.question.id}', bearer=bearer)
        self.assertEqual(body['data']['votes'], 1)
        self.assertEqual(body['data']['user_context']['vote'], 1)

        # vote 0 retracts
        response, body = self.api(
            'POST', f'/forum/posts/{self.question.id}/vote',
            {'vote': 0}, bearer=bearer)
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(body['data'], {'votes': 0, 'user_vote': 0})

        response, body = self.api(
            'POST', f'/forum/posts/{self.question.id}/vote',
            {'vote': 5}, bearer=bearer)
        self.assert_api_error(response, body, 422, 'validation_error')

    def test_vote_own_post_rejected(self):
        bearer = self.make_access_token(self.user_asker)
        response, body = self.api(
            'POST', f'/forum/posts/{self.question.id}/vote',
            {'vote': 1}, bearer=bearer)
        self.assert_api_error(response, body, 422, 'own_post')

    # -- karma gates -------------------------------------------------------

    def test_karma_required_to_ask(self):
        bearer = self.make_access_token(self.user_newbie)
        response, body = self.api('POST', '/forum/posts', {
            'forum_id': self.forum.id,
            'name': 'Newbie question',
            'content': '<p>Not enough karma for this.</p>',
        }, bearer=bearer)
        self.assert_api_error(response, body, 403, 'karma_required')
        self.assertEqual(body['error']['details']['required'], self.forum.karma_ask)

    def test_karma_required_to_upvote(self):
        bearer = self.make_access_token(self.user_newbie)
        response, body = self.api(
            'POST', f'/forum/posts/{self.question.id}/vote',
            {'vote': 1}, bearer=bearer)
        self.assert_api_error(response, body, 403, 'karma_required')
        self.assertEqual(
            body['error']['details']['required'], self.forum.karma_upvote)

    # -- comments ----------------------------------------------------------

    def test_comment(self):
        bearer = self.make_access_token(self.user_voter)
        response, body = self.api(
            'POST', f'/forum/posts/{self.question.id}/comments',
            {'content': 'Great question by the way'}, bearer=bearer)
        self.assertEqual(response.status_code, 200, body)
        comment_id = body['data']['id']
        self.assertIn('Great question by the way', body['data']['body'])
        self.assertEqual(body['data']['author']['name'], 'Forum Voter')

        response, body = self.api('GET', f'/forum/posts/{self.question.id}')
        self.assertIn(comment_id, [c['id'] for c in body['data']['comments']])

    # -- profiles ----------------------------------------------------------

    def test_user_profile(self):
        response, body = self.api('GET', f'/forum/users/{self.user_asker.id}')
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertEqual(data['id'], self.user_asker.id)
        self.assertEqual(data['name'], 'Forum Asker')
        # karma moved since setUpClass (karma_gen_question_new on ask)
        self.assertEqual(data['karma'], self.user_asker.karma)
        self.assertEqual(data['post_count'], 1)
        self.assertEqual(data['answer_count'], 0)
        self.assertIsInstance(data['badges'], list)
        self.assertTrue(data['joined'])

    def test_user_profile_unpublished_and_unknown(self):
        # voter never published their profile -> hidden from other users
        response, body = self.api('GET', f'/forum/users/{self.user_voter.id}')
        self.assert_api_error(response, body, 403, 'forbidden')
        response, body = self.api('GET', '/forum/users/99999999')
        self.assert_api_error(response, body, 404, 'not_found')
