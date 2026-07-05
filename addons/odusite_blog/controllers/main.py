import json

from odoo import fields, http
from odoo.fields import Domain
from odoo.http import request
from odoo.tools import sql

from odoo.addons.odusite_base.controllers.api import (
    API_PREFIX,
    ApiError,
    list_meta,
    odusite_route,
    parse_pagination,
)
from odoo.addons.odusite_base.lib import serializers

POST_ORDER_WHITELIST = {
    'published_desc': 'post_date desc, id desc',
    'name': 'name asc, id desc',
    'visits': 'visits desc, id desc',
}
RELATED_POSTS_COUNT = 4


class OdusiteBlogController(http.Controller):

    def _published_post_domain(self):
        return Domain.AND([
            request.website.website_domain(),
            [('is_published', '=', True), ('post_date', '<=', fields.Datetime.now())],
        ])

    def _ref_id(self, value, label):
        _, record_id = serializers.unslug(str(value))
        if not record_id:
            raise ApiError(400, 'bad_request', f'Invalid {label}: {value}')
        return record_id

    def _post_domain(self, blog=None, tag=None, search=None, date_from=None,
                     date_to=None, **kwargs):
        domain = self._published_post_domain()
        if blog:
            domain &= Domain('blog_id', '=', self._ref_id(blog, 'blog'))
        if tag:
            domain &= Domain('tag_ids', 'in', [self._ref_id(tag, 'tag')])
        for param, value, operator in (('date_from', date_from, '>='),
                                       ('date_to', date_to, '<=')):
            if not value:
                continue
            try:
                fields.Date.to_date(str(value))
            except ValueError:
                raise ApiError(400, 'bad_request', f'Invalid {param}: {value} (expected YYYY-MM-DD).')
            domain &= Domain('post_date', operator, str(value))
        if search:
            domain &= Domain.OR([
                [('name', 'ilike', search)],
                [('subtitle', 'ilike', search)],
                [('content', 'ilike', search)],
            ])
        return domain

    def _post_cover(self, post):
        """Cover image URL extracted from the cover_properties JSON
        (website.cover_properties.mixin stores it as a CSS background-image)."""
        try:
            properties = json.loads(post.cover_properties or '{}')
        except ValueError:
            return None
        image = properties.get('background-image', 'none')
        if isinstance(image, str) and image.startswith('url(') and image.endswith(')'):
            return image[4:-1].strip('\'"') or None
        return None

    def _serialize_post(self, post):
        blog = post.blog_id
        return {
            'id': post.id,
            'slug': serializers.slug(post),
            'name': post.name,
            'subtitle': post.subtitle or '',
            'teaser': post.teaser or '',
            'cover': self._post_cover(post),
            'author': {
                'name': post.author_name or '',
                'avatar': serializers.image_url(post, 'author_avatar'),
            },
            'tags': [
                {'id': tag.id, 'slug': serializers.slug(tag), 'name': tag.name}
                for tag in post.tag_ids
            ],
            'post_date': serializers.datetime_utc(post.post_date),
            'blog': {'id': blog.id, 'slug': serializers.slug(blog), 'name': blog.name},
        }

    def _serialize_post_ref(self, post):
        if not post:
            return None
        return {'id': post.id, 'slug': serializers.slug(post), 'name': post.name}

    def _get_published_post(self, ref):
        _, post_id = serializers.unslug(str(ref))
        if not post_id:
            raise ApiError(404, 'not_found', 'Blog post not found.')
        post = request.env['blog.post'].sudo().browse(post_id).exists()
        if not post or not post.filtered_domain(self._published_post_domain()):
            raise ApiError(404, 'not_found', 'Blog post not found.')
        return post

    @odusite_route(f'{API_PREFIX}/blog/blogs', methods=['GET'])
    def blogs(self, **kwargs):
        blogs = request.env['blog.blog'].sudo().search(
            request.website.website_domain(), order='sequence, id')
        counts = {
            blog.id: count
            for blog, count in request.env['blog.post'].sudo()._read_group(
                self._published_post_domain(), ['blog_id'], ['__count'])
        }
        return [
            {
                'id': blog.id,
                'slug': serializers.slug(blog),
                'name': blog.name,
                'subtitle': blog.subtitle or '',
                'post_count': counts.get(blog.id, 0),
            }
            for blog in blogs
        ]

    @odusite_route(f'{API_PREFIX}/blog/posts', methods=['GET'])
    def posts(self, **kwargs):
        page, limit, offset, order = parse_pagination(
            kwargs, order_whitelist=POST_ORDER_WHITELIST, default_order='published_desc')
        domain = self._post_domain(**kwargs)
        Post = request.env['blog.post'].sudo()
        total = Post.search_count(domain)
        posts = Post.search(domain, limit=limit, offset=offset, order=order)
        return [self._serialize_post(post) for post in posts], list_meta(total, page, limit)

    @odusite_route(f'{API_PREFIX}/blog/posts/<string:post_ref>', methods=['GET'])
    def post_detail(self, post_ref, **kwargs):
        post = self._get_published_post(post_ref)
        Post = request.env['blog.post'].sudo()
        blog_domain = Domain.AND([
            self._published_post_domain(),
            [('blog_id', '=', post.blog_id.id), ('id', '!=', post.id)],
        ])
        prev_post = Post.search(
            Domain.AND([blog_domain, Domain.OR([
                [('post_date', '<', post.post_date)],
                [('post_date', '=', post.post_date), ('id', '<', post.id)],
            ])]),
            order='post_date desc, id desc', limit=1)
        next_post = Post.search(
            Domain.AND([blog_domain, Domain.OR([
                [('post_date', '>', post.post_date)],
                [('post_date', '=', post.post_date), ('id', '>', post.id)],
            ])]),
            order='post_date asc, id asc', limit=1)
        related = Post
        if post.tag_ids:
            related = Post.search(
                Domain.AND([
                    self._published_post_domain(),
                    [('id', '!=', post.id), ('tag_ids', 'in', post.tag_ids.ids)],
                ]),
                order='post_date desc, id desc', limit=RELATED_POSTS_COUNT)
        data = self._serialize_post(post)
        data.update({
            'content': serializers.html_field(post, 'content'),
            'seo': serializers.seo(post),
            'visits': post.visits,
            'prev': self._serialize_post_ref(prev_post),
            'next': self._serialize_post_ref(next_post),
            'related': [self._serialize_post(related_post) for related_post in related],
        })
        # Write-through counter, skips the row when locked (like the stock
        # website_blog controller).
        sql.increment_fields_skiplock(post, 'visits')
        return data

    @odusite_route(f'{API_PREFIX}/blog/tags', methods=['GET'])
    def tags(self, **kwargs):
        groups = request.env['blog.post'].sudo()._read_group(
            self._published_post_domain(), ['tag_ids'], ['__count'])
        items = [
            {
                'id': tag.id,
                'slug': serializers.slug(tag),
                'name': tag.name,
                'category': tag.category_id.name or None,
                'post_count': count,
            }
            for tag, count in groups if tag
        ]
        return sorted(items, key=lambda item: item['name'].upper())
