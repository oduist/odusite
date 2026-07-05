"""Odusite eLearning API (see specs/modules/odusite_slides.md).

Catalog visibility mirrors the upstream /slides controller
(``website_domain()`` + ``is_visible`` + published). Content lock rule
(spec): a slide is accessible when it ``is_preview``, or its channel has
public visibility, or the JWT user is an enrolled member. Membership,
completion and quizzes reuse the stock slide.channel / slide.slide methods.
"""

import base64

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import content_disposition, request
from odoo.tools.mimetypes import guess_mimetype

from odoo.addons.odusite_base.controllers.api import (
    API_PREFIX,
    ApiError,
    list_meta,
    odusite_route,
    parse_pagination,
)
from odoo.addons.odusite_base.lib import serializers

COURSE_ORDERS = {
    'default': 'sequence asc, id asc',
    'newest': 'create_date desc, id desc',
    'name': 'name asc, id asc',
}


class OdusiteSlidesController(http.Controller):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _channel_domain(self):
        """Mirror slide.channel._search_get_detail: website domain +
        is_visible (public visibility, or connected/member for JWT users)
        + explicit publish filter."""
        return (
            request.website.website_domain()
            + [('is_visible', '=', True), ('is_published', '=', True)]
        )

    def _get_channel(self, id_or_slug):
        _name, channel_id = serializers.unslug(str(id_or_slug))
        if not channel_id:
            raise ApiError(404, 'not_found', 'Course not found.')
        channel = request.env['slide.channel'].search(
            self._channel_domain() + [('id', '=', channel_id)], limit=1)
        if not channel:
            raise ApiError(404, 'not_found', 'Course not found.')
        return channel

    def _member_partner(self):
        if request.env.user._is_public():
            return None
        return request.env.user.partner_id

    def _membership(self, channel):
        """sudo slide.channel.partner of the JWT user (enrolled only)."""
        partner = self._member_partner()
        if not partner:
            return request.env['slide.channel.partner'].sudo()
        return request.env['slide.channel.partner'].sudo().search([
            ('channel_id', '=', channel.id),
            ('partner_id', '=', partner.id),
            ('member_status', '!=', 'invited'),
        ], limit=1)

    def _is_member(self, channel):
        return bool(self._membership(channel))

    def _slide_accessible(self, channel, slide, is_member=None):
        """Spec lock rule: preview OR public-visibility course OR member."""
        if slide.sudo().is_preview:
            return True
        if channel.sudo().visibility == 'public':
            return True
        if is_member is None:
            is_member = self._is_member(channel)
        return is_member

    def _get_slide(self, channel, slide_id):
        slide = request.env['slide.slide'].sudo().browse(int(slide_id)).exists()
        website = request.website
        if (
            not slide
            or slide.channel_id != channel
            or slide.is_category
            or not slide.website_published
            or (slide.website_id and slide.website_id != website)
        ):
            raise ApiError(404, 'not_found', 'Content not found.')
        return slide

    def _serialize_channel_tag(self, tag):
        tag = tag.sudo()
        return {
            'id': tag.id,
            'name': tag.name,
            'group': tag.group_id.name or None,
        }

    def _serialize_channel(self, channel, is_member=None):
        channel_sudo = channel.sudo()
        if is_member is None:
            is_member = self._is_member(channel)
        return {
            'id': channel.id,
            'slug': serializers.slug(channel),
            'name': channel_sudo.name,
            'description_short': serializers.html_field(channel, 'description_short'),
            'cover': serializers.image_url(channel, 'image_1024'),
            'channel_type': channel_sudo.channel_type,
            'total_time': round(channel_sudo.total_time, 2),
            'slide_count': channel_sudo.total_slides,
            'members_count': channel_sudo.members_count,
            'rating_avg': round(channel_sudo.rating_avg, 2),
            'tags': [self._serialize_channel_tag(tag) for tag in channel_sudo.tag_ids],
            'enroll': channel_sudo.enroll,
            'is_member': is_member,
        }

    def _curriculum(self, channel, is_member):
        """Curriculum grouped by category, published slides only (mirrors
        the public branch of _get_channel_slides_base_domain)."""
        base_domain = (
            request.website.website_domain()
            + [('channel_id', '=', channel.id), ('is_category', '=', False),
               ('website_published', '=', True)]
        )
        channel_sudo = channel.sudo()
        category_data = channel_sudo._get_categorized_slides(
            base_domain,
            order=request.env['slide.slide']._order_by_strategy['sequence'],
            force_void=False,
        )
        completed_ids = set()
        partner = self._member_partner()
        if partner and is_member:
            completed_ids = set(
                request.env['slide.slide.partner'].sudo().search([
                    ('channel_id', '=', channel.id),
                    ('partner_id', '=', partner.id),
                    ('completed', '=', True),
                ]).mapped('slide_id').ids)
        return [
            {
                'category': category['category'].name if category['category'] else None,
                'slides': [
                    {
                        'id': slide.id,
                        'slug': serializers.slug(slide),
                        'name': slide.name,
                        'type': slide.slide_category,
                        'duration': round(slide.completion_time, 2),
                        'is_preview': slide.is_preview,
                        'is_locked': not self._slide_accessible(
                            channel, slide, is_member=is_member),
                        'completed': slide.id in completed_ids,
                    }
                    for slide in category['slides']
                ],
            }
            for category in category_data
        ]

    def _serialize_channel_detail(self, channel):
        is_member = self._is_member(channel)
        data = self._serialize_channel(channel, is_member=is_member)
        channel_sudo = channel.sudo()
        membership = self._membership(channel)
        data.update({
            'description_html': serializers.html_field(channel, 'description_html')
                or serializers.html_field(channel, 'description'),
            'curriculum': self._curriculum(channel, is_member),
            'completion': membership.completion if membership else None,
            'prerequisites': [
                {
                    'id': prerequisite.id,
                    'slug': serializers.slug(prerequisite),
                    'name': prerequisite.name,
                }
                for prerequisite in channel_sudo.prerequisite_channel_ids
                if prerequisite.is_published
            ],
            'seo': serializers.seo(channel),
        })
        return data

    # ------------------------------------------------------------------
    # Catalog
    # ------------------------------------------------------------------

    @odusite_route(f'{API_PREFIX}/courses', methods=['GET'])
    def courses_list(self, **kwargs):
        page, limit, offset, order = parse_pagination(
            kwargs, order_whitelist=COURSE_ORDERS, default_order='default')

        domain = self._channel_domain()
        if kwargs.get('tag'):
            _name, tag_id = serializers.unslug(str(kwargs['tag']))
            if not tag_id:
                raise ApiError(400, 'bad_request', 'Invalid tag.')
            domain += [('tag_ids', 'in', [tag_id])]
        if kwargs.get('search'):
            domain += ['|', ('name', 'ilike', kwargs['search']),
                       ('description_short', 'ilike', kwargs['search'])]

        Channel = request.env['slide.channel']
        total = Channel.search_count(domain)
        channels = Channel.search(domain, limit=limit, offset=offset, order=order)
        return (
            [self._serialize_channel(channel) for channel in channels],
            list_meta(total, page, limit),
        )

    @odusite_route(f'{API_PREFIX}/courses/<string:id_or_slug>', methods=['GET'])
    def course_detail(self, id_or_slug, **kwargs):
        channel = self._get_channel(id_or_slug)
        return self._serialize_channel_detail(channel)

    # ------------------------------------------------------------------
    # Membership
    # ------------------------------------------------------------------

    @odusite_route(f'{API_PREFIX}/courses/<int:channel_id>/join',
                   methods=['POST'], auth_user=True)
    def course_join(self, channel_id, **kwargs):
        channel = self._get_channel(channel_id)
        enroll = channel.sudo().enroll
        if enroll == 'invite':
            raise ApiError(403, 'invite_only',
                           'This course is only accessible on invitation.')
        if enroll != 'public':
            # 'payment' when website_sale_slides is installed (phase 2)
            raise ApiError(409, 'payment_required',
                           'This course requires a purchase to enroll.')
        # stock membership method, same call as /slides/channel/join
        channel._action_add_members(request.env.user.partner_id)
        membership = self._membership(channel)
        return {
            'joined': True,
            'is_member': bool(membership),
            'completion': membership.completion if membership else 0,
        }

    # ------------------------------------------------------------------
    # Content
    # ------------------------------------------------------------------

    def _video_data(self, slide):
        provider = slide.video_source_type
        embed_url = None
        if provider == 'youtube' and slide.youtube_id:
            # same targets as slide.slide._compute_embed_code
            embed_url = f'https://www.youtube-nocookie.com/embed/{slide.youtube_id}'
        elif provider == 'google_drive' and slide.google_drive_id:
            provider = 'drive'
            embed_url = f'https://drive.google.com/file/d/{slide.google_drive_id}/preview'
        elif provider == 'vimeo' and slide.vimeo_id:
            if '/' in slide.vimeo_id:
                vimeo_id, vimeo_token = slide.vimeo_id.split('/')
                embed_url = (f'https://player.vimeo.com/video/{vimeo_id}'
                             f'?h={vimeo_token}&badge=0&autopause=0&player_id=0')
            else:
                embed_url = (f'https://player.vimeo.com/video/{slide.vimeo_id}'
                             f'?badge=0&autopause=0&player_id=0')
        if not embed_url:
            return None
        return {'provider': provider, 'embed_url': embed_url}

    @odusite_route(f'{API_PREFIX}/courses/<int:channel_id>/slides/<int:slide_id>',
                   methods=['GET'])
    def slide_content(self, channel_id, slide_id, **kwargs):
        channel = self._get_channel(channel_id)
        slide = self._get_slide(channel, slide_id)
        is_member = self._is_member(channel)
        if not self._slide_accessible(channel, slide, is_member=is_member):
            raise ApiError(403, 'members_only',
                           'Join the course to access this content.')

        user_vote = 0
        completed = False
        partner = self._member_partner()
        if partner:
            slide_partner = request.env['slide.slide.partner'].sudo().search([
                ('slide_id', '=', slide.id),
                ('partner_id', '=', partner.id),
            ], limit=1)
            user_vote = slide_partner.vote if slide_partner else 0
            completed = slide_partner.completed if slide_partner else False

        data = {
            'id': slide.id,
            'slug': serializers.slug(slide),
            'name': slide.name,
            'type': slide.slide_category,
            'duration': round(slide.completion_time, 2),
            'is_preview': slide.is_preview,
            'completed': completed,
            'likes': slide.likes,
            'dislikes': slide.dislikes,
            'user_vote': user_vote,
            'resources': [
                {
                    'name': resource.name,
                    'url': resource.link if resource.resource_type == 'url'
                           else resource.download_url,
                }
                for resource in slide.slide_resource_ids
            ],
        }
        if slide.slide_category == 'article':
            data['html_content'] = slide.html_content or ''
        video = self._video_data(slide) if slide.slide_category == 'video' else None
        if video:
            data['video'] = video
        if slide.binary_content:
            data['binary_url'] = (
                f'{API_PREFIX}/courses/{channel.id}/slides/{slide.id}/download')
        return data

    @odusite_route(
        f'{API_PREFIX}/courses/<int:channel_id>/slides/<int:slide_id>/download',
        methods=['GET'])
    def slide_download(self, channel_id, slide_id, **kwargs):
        channel = self._get_channel(channel_id)
        slide = self._get_slide(channel, slide_id)
        if not self._slide_accessible(channel, slide):
            raise ApiError(403, 'members_only',
                           'Join the course to access this content.')
        if not slide.binary_content:
            raise ApiError(404, 'not_found', 'This content has no attachment.')
        content = base64.b64decode(slide.binary_content)
        mimetype = guess_mimetype(content, default='application/octet-stream')
        return request.make_response(content, [
            ('Content-Type', mimetype),
            ('Content-Length', len(content)),
            ('Content-Disposition', content_disposition(slide.name)),
        ])

    # ------------------------------------------------------------------
    # Completion
    # ------------------------------------------------------------------

    @odusite_route(
        f'{API_PREFIX}/courses/<int:channel_id>/slides/<int:slide_id>/complete',
        methods=['POST'], auth_user=True)
    def slide_complete(self, channel_id, slide_id, **kwargs):
        channel = self._get_channel(channel_id)
        slide_sudo = self._get_slide(channel, slide_id)
        membership = self._membership(channel)
        if not membership:
            raise ApiError(403, 'members_only',
                           'Join the course to track your progress.')
        # same checks as the upstream _slide_mark_completed
        if slide_sudo.slide_category == 'quiz' or slide_sudo.question_ids:
            raise ApiError(422, 'validation_error',
                           'Quiz content is completed by submitting the quiz.')
        slide = request.env['slide.slide'].browse(slide_sudo.id)
        try:
            if not slide.can_self_mark_completed:
                raise ApiError(403, 'forbidden',
                               'This content cannot be marked as completed.')
            slide.action_mark_completed()
        except (AccessError, UserError):
            raise ApiError(403, 'forbidden',
                           'This content cannot be marked as completed.')
        return {
            'completed': True,
            'completion': self._membership(channel).completion,
        }

    # ------------------------------------------------------------------
    # Quiz
    # ------------------------------------------------------------------

    def _quiz_questions(self, slide, with_correction):
        return [
            {
                'id': question.id,
                'question': question.question,
                'answers': [
                    {
                        'id': answer.id,
                        'text': answer.text_value,
                        # only revealed once the quiz is completed (upstream rule)
                        'is_correct': answer.is_correct if with_correction else None,
                    }
                    for answer in question.sudo().answer_ids
                ],
            }
            for question in slide.sudo().question_ids
        ]

    @odusite_route(
        f'{API_PREFIX}/courses/<int:channel_id>/slides/<int:slide_id>/quiz',
        methods=['GET'])
    def slide_quiz_get(self, channel_id, slide_id, **kwargs):
        channel = self._get_channel(channel_id)
        slide = self._get_slide(channel, slide_id)
        if not self._slide_accessible(channel, slide):
            raise ApiError(403, 'members_only',
                           'Join the course to access this quiz.')
        partner = self._member_partner()
        quiz_info = slide.sudo()._compute_quiz_info(
            partner or request.env.user.partner_id, quiz_done=False)[slide.id]
        completed = False
        if partner:
            slide_partner = request.env['slide.slide.partner'].sudo().search([
                ('slide_id', '=', slide.id), ('partner_id', '=', partner.id),
            ], limit=1)
            completed = slide_partner.completed if slide_partner else False
        return {
            'questions': self._quiz_questions(slide, with_correction=completed),
            'completed': completed,
            'karma_max': quiz_info['quiz_karma_max'],
            'karma_gain': quiz_info['quiz_karma_gain'],
            'karma_won': quiz_info['quiz_karma_won'],
            'attempts_count': quiz_info['quiz_attempts_count'],
        }

    @odusite_route(
        f'{API_PREFIX}/courses/<int:channel_id>/slides/<int:slide_id>/quiz',
        methods=['POST'], auth_user=True)
    def slide_quiz_submit(self, channel_id, slide_id, **kwargs):
        channel = self._get_channel(channel_id)
        slide_sudo = self._get_slide(channel, slide_id)
        if not self._membership(channel):
            raise ApiError(403, 'members_only',
                           'Join the course to submit this quiz.')

        answers = kwargs.get('answers')
        if not isinstance(answers, dict) or not answers:
            raise ApiError(422, 'validation_error', 'Missing answers.',
                           {'fields': {'answers': 'required'}})
        try:
            answer_ids = [int(answer_id) for answer_id in answers.values()]
        except (TypeError, ValueError):
            raise ApiError(422, 'validation_error', 'Invalid answer ids.',
                           {'fields': {'answers': 'invalid'}})

        # replicate the stock /slides/slide/quiz/submit flow
        slide = request.env['slide.slide'].browse(slide_sudo.id)
        if slide.user_has_completed:
            raise ApiError(409, 'quiz_done', 'This quiz is already completed.')

        all_questions = request.env['slide.question'].sudo().search(
            [('slide_id', '=', slide.id)])
        user_answers = request.env['slide.answer'].sudo().search(
            [('id', 'in', answer_ids)])
        if set(user_answers.question_id.ids) != set(all_questions.ids) \
                or len(user_answers) != len(all_questions):
            raise ApiError(422, 'quiz_incomplete',
                           'All questions must be answered.')

        user_bad_answers = user_answers.filtered(lambda answer: not answer.is_correct)

        slide.action_set_viewed(quiz_attempts_inc=True)
        quiz_info = slide_sudo._compute_quiz_info(
            request.env.user.partner_id, quiz_done=True)[slide.id]
        if not user_bad_answers:
            try:
                slide._action_mark_completed()
            except UserError as exc:
                raise ApiError(403, 'forbidden',
                               str(exc.args[0]) if exc.args else str(exc))

        membership = self._membership(channel)
        return {
            'answers': {
                str(answer.question_id.id): {
                    'answer_id': answer.id,
                    'is_correct': answer.is_correct,
                    'comment': answer.comment or None,
                }
                for answer in user_answers
            },
            'completed': not user_bad_answers,
            'completion': membership.completion if membership else 0,
            'karma_won': quiz_info['quiz_karma_won'] if not user_bad_answers else 0,
            'karma_gain': quiz_info['quiz_karma_gain'],
            'attempts_count': quiz_info['quiz_attempts_count'],
        }
