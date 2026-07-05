"""Odusite forum API (see specs/modules/odusite_forum.md).

Read endpoints are public and mirror the upstream website_forum visibility
(website domain + active state + ``can_view``; forum privacy is enforced by
record rules). Action endpoints require a JWT; karma requirements are
enforced by the stock forum model methods (AccessError) and mapped to
403 ``karma_required`` with the required karma extracted from the message.
"""

import re

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import request
from odoo.tools import is_html_empty
from odoo.tools.mail import plaintext2html

from odoo.addons.odusite_base.controllers.api import (
    API_PREFIX,
    ApiError,
    list_meta,
    odusite_route,
    parse_pagination,
)
from odoo.addons.odusite_base.lib import serializers

POST_ORDERS = {
    'relevance': 'relevancy desc, id desc',
    'newest': 'create_date desc, id desc',
    'votes': 'vote_count desc, id desc',
    'activity': 'last_activity_date desc, id desc',
}
POST_FILTERS = ('all', 'unanswered', 'solved')


def _karma_error(exc):
    """Map a karma AccessError raised by website_forum model methods to
    403 karma_required, extracting the required amount when possible."""
    message = str(exc.args[0]) if exc.args else str(exc)
    match = re.search(r'\d+', message)
    if 'karma' in message.lower() and match:
        return ApiError(403, 'karma_required', message,
                        {'required': int(match.group(0))})
    return ApiError(403, 'forbidden', 'You are not allowed to perform this action.')


class OdusiteForumController(http.Controller):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _question_domain(self):
        """Mirror forum.post._search_get_detail base domain."""
        return (
            request.website.website_domain()
            + [('state', '=', 'active'), ('can_view', '=', True),
               ('parent_id', '=', False)]
        )

    def _get_question(self, id_or_slug):
        _name, post_id = serializers.unslug(str(id_or_slug))
        if not post_id:
            raise ApiError(404, 'not_found', 'Post not found.')
        post = request.env['forum.post'].search(
            self._question_domain() + [('id', '=', post_id)], limit=1)
        if not post:
            raise ApiError(404, 'not_found', 'Post not found.')
        return post

    def _get_post_for_action(self, post_id):
        """Fetch any post (question or answer) for a JWT action; record rules
        of the JWT user apply."""
        post = request.env['forum.post'].browse(int(post_id)).exists()
        if not post or not post.can_view:
            raise ApiError(404, 'not_found', 'Post not found.')
        return post

    def _serialize_author(self, user):
        user = user.sudo()
        if not user:
            return None
        return {
            'id': user.id,
            'name': user.name,
            # public avatar route from website_profile (published users with karma)
            'avatar': f'/profile/avatar/{user.id}',
            'karma': user.karma,
        }

    def _serialize_post(self, post):
        return {
            'id': post.id,
            'slug': serializers.slug(post),
            'name': post.name,
            'forum': {
                'id': post.forum_id.id,
                'slug': serializers.slug(post.forum_id),
                'name': post.forum_id.name,
            },
            'tags': [
                {'id': tag.id, 'slug': serializers.slug(tag), 'name': tag.name}
                for tag in post.tag_ids
            ],
            'votes': post.vote_count,
            'answer_count': post.child_count,
            'has_validated_answer': post.has_validated_answer,
            'views': post.views,
            'author': self._serialize_author(post.create_uid),
            'last_activity': serializers.datetime_utc(post.last_activity_date),
        }

    def _serialize_comments(self, post):
        # website_message_ids is domain-limited to comment/email messages
        return [
            {
                'id': message.id,
                'body': message.body,
                'author': {
                    'id': message.author_id.id,
                    'name': message.author_id.name,
                },
                'create_date': serializers.datetime_utc(message.create_date),
            }
            for message in post.sudo().website_message_ids.sorted('id')
        ]

    def _serialize_answer(self, answer):
        return {
            'id': answer.id,
            'content_html': serializers.html_field(answer, 'content'),
            'votes': answer.vote_count,
            'is_correct': answer.is_correct,
            'author': self._serialize_author(answer.create_uid),
            'create_date': serializers.datetime_utc(answer.create_date),
            'comments': self._serialize_comments(answer),
        }

    def _user_context(self, post):
        return {
            'vote': post.user_vote,
            'is_favourite': post.user_favourite,
            'can_answer': post.can_answer,
            'can_comment': post.can_comment,
            'can_upvote': post.can_upvote,
            'can_downvote': post.can_downvote,
            'can_accept': post.can_accept,
            'can_edit': post.can_edit,
        }

    def _serialize_question_detail(self, question):
        data = self._serialize_post(question)
        answers = question.child_ids.filtered(
            lambda answer: answer.state == 'active' and answer.can_view)
        data.update({
            'content_html': serializers.html_field(question, 'content'),
            'answers': [self._serialize_answer(answer) for answer in answers],
            'comments': self._serialize_comments(question),
        })
        if not request.env.user._is_public():
            data['user_context'] = self._user_context(question)
        return data

    # ------------------------------------------------------------------
    # Read endpoints (public)
    # ------------------------------------------------------------------

    @odusite_route(f'{API_PREFIX}/forum/forums', methods=['GET'])
    def forums_list(self, **kwargs):
        forums = request.env['forum.forum'].search(
            request.website.website_domain())
        return [
            {
                'id': forum.id,
                'slug': serializers.slug(forum),
                'name': forum.name,
                'description': forum.description or '',
                'mode': forum.mode,
                'post_count': forum.total_posts,
            }
            for forum in forums
        ]

    @odusite_route(f'{API_PREFIX}/forum/posts', methods=['GET'])
    def posts_list(self, **kwargs):
        page, limit, offset, order = parse_pagination(
            kwargs, order_whitelist=POST_ORDERS, default_order='relevance')

        domain = self._question_domain()
        if kwargs.get('forum'):
            _name, forum_id = serializers.unslug(str(kwargs['forum']))
            if not forum_id:
                raise ApiError(400, 'bad_request', 'Invalid forum.')
            domain += [('forum_id', '=', forum_id)]
        if kwargs.get('tag'):
            _name, tag_id = serializers.unslug(str(kwargs['tag']))
            if not tag_id:
                raise ApiError(400, 'bad_request', 'Invalid tag.')
            domain += [('tag_ids', 'in', [tag_id])]

        post_filter = kwargs.get('filter') or 'all'
        if post_filter not in POST_FILTERS:
            raise ApiError(400, 'bad_request', f'Unsupported filter: {post_filter}',
                           {'allowed': list(POST_FILTERS)})
        if post_filter == 'unanswered':
            domain += [('child_ids', '=', False)]
        elif post_filter == 'solved':
            domain += [('has_validated_answer', '=', True)]

        if kwargs.get('search'):
            domain += ['|', ('name', 'ilike', kwargs['search']),
                       ('plain_content', 'ilike', kwargs['search'])]

        Post = request.env['forum.post']
        total = Post.search_count(domain)
        posts = Post.search(domain, limit=limit, offset=offset, order=order)
        return (
            [self._serialize_post(post) for post in posts],
            list_meta(total, page, limit),
        )

    @odusite_route(f'{API_PREFIX}/forum/posts/<string:id_or_slug>', methods=['GET'])
    def post_detail(self, id_or_slug, **kwargs):
        question = self._get_question(id_or_slug)
        question.sudo()._set_viewed()
        return self._serialize_question_detail(question)

    @odusite_route(f'{API_PREFIX}/forum/tags', methods=['GET'])
    def tags_list(self, **kwargs):
        domain = []
        if kwargs.get('forum'):
            _name, forum_id = serializers.unslug(str(kwargs['forum']))
            if not forum_id:
                raise ApiError(400, 'bad_request', 'Invalid forum.')
            domain += [('forum_id', '=', forum_id)]
        tags = request.env['forum.tag'].search(domain, order='posts_count desc, name')
        return [
            {
                'id': tag.id,
                'slug': serializers.slug(tag),
                'name': tag.name,
                'post_count': tag.posts_count,
            }
            for tag in tags
        ]

    @odusite_route(f'{API_PREFIX}/forum/users/<int:user_id>', methods=['GET'])
    def user_profile(self, user_id, **kwargs):
        # mirror website_profile._check_user_profile_access
        user_sudo = request.env['res.users'].sudo().browse(user_id).exists()
        if not user_sudo:
            raise ApiError(404, 'not_found', 'User not found.')
        if user_sudo.id != request.env.user.id:
            if not user_sudo.website_published:
                raise ApiError(403, 'forbidden', 'This profile is private.')
            karma_min = request.website.sudo().karma_profile_min
            if request.env.user.karma < karma_min:
                raise ApiError(403, 'karma_required',
                               'Not enough karma to view this profile.',
                               {'required': karma_min})

        badges = {}
        for badge_user in user_sudo.badge_ids:
            key = (badge_user.badge_id.id, badge_user.level or False)
            if key not in badges:
                badges[key] = {
                    'name': badge_user.badge_id.name,
                    'level': badge_user.level or None,
                    'count': 0,
                }
            badges[key]['count'] += 1

        PostSudo = request.env['forum.post'].sudo()
        base_domain = request.website.website_domain() + [
            ('create_uid', '=', user_sudo.id), ('state', '=', 'active')]
        return {
            'id': user_sudo.id,
            'name': user_sudo.name,
            'avatar': f'/profile/avatar/{user_sudo.id}',
            'karma': user_sudo.karma,
            'badges': list(badges.values()),
            'joined': serializers.date_iso(
                user_sudo.create_date and user_sudo.create_date.date()),
            'post_count': PostSudo.search_count(
                base_domain + [('parent_id', '=', False)]),
            'answer_count': PostSudo.search_count(
                base_domain + [('parent_id', '!=', False)]),
        }

    # ------------------------------------------------------------------
    # Actions (JWT)
    # ------------------------------------------------------------------

    def _tag_commands(self, forum, tags):
        """Build tag write commands via the stock forum helper. Existing tags
        are given by id, new ones by name (created if karma allows, silently
        skipped otherwise, as upstream does)."""
        if not tags:
            return []
        if not isinstance(tags, list):
            raise ApiError(422, 'validation_error', 'tags must be a list.',
                           {'fields': {'tags': 'invalid'}})
        parts = []
        for tag in tags:
            if isinstance(tag, int):
                parts.append(str(tag))
            elif isinstance(tag, str) and tag.strip():
                if tag.strip().isdigit():
                    parts.append(tag.strip())
                else:
                    parts.append('_' + tag.strip())
        return forum._tag_to_write_vals(','.join(parts))

    @odusite_route(f'{API_PREFIX}/forum/posts', methods=['POST'], auth_user=True)
    def post_create(self, **kwargs):
        forum_id = kwargs.get('forum_id')
        if not forum_id:
            raise ApiError(422, 'validation_error', 'Missing forum_id.',
                           {'fields': {'forum_id': 'required'}})
        forum = request.env['forum.forum'].browse(int(forum_id)).exists()
        if not forum:
            raise ApiError(404, 'not_found', 'Forum not found.')
        name = (kwargs.get('name') or '').strip()
        content = kwargs.get('content') or ''
        if not name:
            raise ApiError(422, 'validation_error', 'Title should not be empty.',
                           {'fields': {'name': 'required'}})
        if is_html_empty(content):
            raise ApiError(422, 'validation_error', 'Question should not be empty.',
                           {'fields': {'content': 'required'}})
        if forum.has_pending_post:
            raise ApiError(409, 'pending_post',
                           'You already have a post waiting for validation.')
        try:
            question = request.env['forum.post'].create({
                'forum_id': forum.id,
                'name': name,
                'content': content,
                'parent_id': False,
                'tag_ids': self._tag_commands(forum, kwargs.get('tags')),
            })
        except AccessError as exc:
            raise _karma_error(exc)
        return {
            'id': question.id,
            'slug': serializers.slug(question),
            'state': question.state,
        }

    @odusite_route(f'{API_PREFIX}/forum/posts/<int:post_id>/answers',
                   methods=['POST'], auth_user=True)
    def post_answer(self, post_id, **kwargs):
        question = self._get_post_for_action(post_id)
        if question.parent_id:
            raise ApiError(422, 'validation_error', 'You can only answer questions.')
        content = kwargs.get('content') or ''
        if is_html_empty(content):
            raise ApiError(422, 'validation_error', 'Reply should not be empty.',
                           {'fields': {'content': 'required'}})
        try:
            answer = request.env['forum.post'].create({
                'forum_id': question.forum_id.id,
                'name': 'Re: %s' % (question.name or ''),
                'content': content,
                'parent_id': question.id,
            })
        except (AccessError, UserError) as exc:
            if isinstance(exc, AccessError):
                raise _karma_error(exc)
            raise
        question._update_last_activity()
        return self._serialize_answer(answer)

    @odusite_route(f'{API_PREFIX}/forum/posts/<int:post_id>',
                   methods=['PUT'], auth_user=True)
    def post_edit(self, post_id, **kwargs):
        post = self._get_post_for_action(post_id)
        vals = {}
        if 'content' in kwargs:
            if is_html_empty(kwargs.get('content') or ''):
                raise ApiError(422, 'validation_error', 'Content should not be empty.',
                               {'fields': {'content': 'required'}})
            vals['content'] = kwargs['content']
        if 'name' in kwargs and not post.parent_id:
            if not (kwargs.get('name') or '').strip():
                raise ApiError(422, 'validation_error', 'Title should not be empty.',
                               {'fields': {'name': 'required'}})
            vals['name'] = kwargs['name'].strip()
        if 'tags' in kwargs and not post.parent_id:
            vals['tag_ids'] = self._tag_commands(post.forum_id, kwargs.get('tags'))
        if not vals:
            raise ApiError(422, 'validation_error', 'Nothing to update.')
        try:
            post.write(vals)
        except AccessError as exc:
            raise _karma_error(exc)
        if post.parent_id:
            return self._serialize_answer(post)
        return self._serialize_question_detail(post)

    @odusite_route(f'{API_PREFIX}/forum/posts/<int:post_id>',
                   methods=['DELETE'], auth_user=True)
    def post_delete(self, post_id, **kwargs):
        post = self._get_post_for_action(post_id)
        try:
            if post.parent_id:
                # answers are unlinked (upstream post_delete)
                post.unlink()
            else:
                # questions are archived (upstream question_delete)
                post.write({'active': False})
        except AccessError as exc:
            raise _karma_error(exc)
        return None

    @odusite_route(f'{API_PREFIX}/forum/posts/<int:post_id>/vote',
                   methods=['POST'], auth_user=True)
    def post_vote(self, post_id, **kwargs):
        post = self._get_post_for_action(post_id)
        try:
            target = int(kwargs.get('vote'))
        except (TypeError, ValueError):
            raise ApiError(422, 'validation_error', 'vote must be 1, -1 or 0.',
                           {'fields': {'vote': 'invalid'}})
        if target not in (-1, 0, 1):
            raise ApiError(422, 'validation_error', 'vote must be 1, -1 or 0.',
                           {'fields': {'vote': 'invalid'}})
        if request.env.uid == post.create_uid.id:
            raise ApiError(422, 'own_post', 'It is not allowed to vote for your own post.')
        try:
            # post.vote() toggles one step at a time (upvote from -1 gives 0),
            # so step through until the absolute target value is reached.
            current = post.user_vote
            while current != target:
                result = post.vote(upvote=target > current)
                new = int(result['user_vote'])
                if new == current:  # safety, should not happen
                    break
                current = new
        except AccessError as exc:
            raise _karma_error(exc)
        except UserError as exc:
            raise ApiError(422, 'own_post', str(exc.args[0]) if exc.args else str(exc))
        # vote() writes through sudo internals; drop compute caches so
        # vote_count/user_vote are re-read for the JWT user, not stale values.
        post.invalidate_recordset()
        return {'votes': post.vote_count, 'user_vote': post.user_vote}

    @odusite_route(f'{API_PREFIX}/forum/posts/<int:post_id>/accept',
                   methods=['POST'], auth_user=True)
    def post_accept(self, post_id, **kwargs):
        post = self._get_post_for_action(post_id)
        if not post.parent_id:
            raise ApiError(422, 'validation_error', 'Only answers can be accepted.')
        if request.env.uid == post.create_uid.id:
            raise ApiError(422, 'own_post', 'You cannot accept your own answer.')
        try:
            # same toggle logic as upstream post_toggle_correct
            (post.parent_id.child_ids - post).write({'is_correct': False})
            post.is_correct = not post.is_correct
        except AccessError as exc:
            raise _karma_error(exc)
        return {'is_correct': post.is_correct}

    @odusite_route(f'{API_PREFIX}/forum/posts/<int:post_id>/comments',
                   methods=['POST'], auth_user=True)
    def post_comment(self, post_id, **kwargs):
        post = self._get_post_for_action(post_id)
        content = (kwargs.get('content') or '').strip()
        if not content:
            raise ApiError(422, 'validation_error', 'Comment should not be empty.',
                           {'fields': {'content': 'required'}})
        question = post.parent_id or post
        try:
            message = post.with_context(
                mail_post_autofollow_author_skip=True,
            ).message_post(
                body=plaintext2html(content),
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )
        except AccessError as exc:
            raise _karma_error(exc)
        question._update_last_activity()
        message = message.sudo()
        return {
            'id': message.id,
            'body': message.body,
            'author': {
                'id': message.author_id.id,
                'name': message.author_id.name,
            },
            'create_date': serializers.datetime_utc(message.create_date),
        }

    @odusite_route(f'{API_PREFIX}/forum/posts/<int:post_id>/favourite',
                   methods=['POST'], auth_user=True)
    def post_favourite(self, post_id, **kwargs):
        question = self._get_post_for_action(post_id)
        if question.parent_id:
            raise ApiError(422, 'validation_error',
                           'Only questions can be marked as favourite.')
        # same as upstream question_toggle_favorite
        favourite = not question.user_favourite
        question.sudo().favourite_ids = [(4 if favourite else 3, request.env.uid)]
        if favourite:
            question.sudo().message_subscribe(request.env.user.partner_id.ids)
        return {'is_favourite': favourite}
