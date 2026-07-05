from datetime import timedelta

from odoo import fields
from odoo.tests.common import tagged

from odoo.addons.odusite_base.tests.common import OdusiteHttpCase


@tagged('post_install', '-at_install')
class TestBlogApi(OdusiteHttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        now = fields.Datetime.now()
        cls.blog = cls.env['blog.blog'].create({
            'name': 'Odusite Test Blog',
            'subtitle': 'All about testing',
        })
        # tag_filter is attached to a single post (filter tests); tag_shared
        # links the two published posts (related-by-tags tests).
        cls.tag_filter = cls.env['blog.tag'].create({'name': 'Odusite Filter Tag'})
        cls.tag_shared = cls.env['blog.tag'].create({'name': 'Odusite Shared Tag'})
        # blog.post.post_date is computed from published_date with an inverse:
        # writing post_date at create time sets published_date, so both the
        # is_published flag and the `post_date <= now` gate are under control.
        cls.post_old = cls.env['blog.post'].create({
            'name': 'Zanzibar Chronicles',
            'blog_id': cls.blog.id,
            'subtitle': 'The older published post',
            'content': '<p>Old post content body</p>',
            'is_published': True,
            'post_date': now - timedelta(days=10),
            'tag_ids': [(6, 0, [cls.tag_shared.id])],
        })
        cls.post_new = cls.env['blog.post'].create({
            'name': 'Bravo Post',
            'blog_id': cls.blog.id,
            'subtitle': 'The newer published post',
            'content': '<p>New post content body</p>',
            'is_published': True,
            'post_date': now - timedelta(days=1),
            'tag_ids': [(6, 0, [cls.tag_filter.id, cls.tag_shared.id])],
        })
        cls.post_unpublished = cls.env['blog.post'].create({
            'name': 'Charlie Draft',
            'blog_id': cls.blog.id,
            'content': '<p>Unpublished content</p>',
            'is_published': False,
            'post_date': now - timedelta(days=2),
        })
        cls.post_future = cls.env['blog.post'].create({
            'name': 'Delta Scheduled',
            'blog_id': cls.blog.id,
            'content': '<p>Future content</p>',
            'is_published': True,
            'post_date': now + timedelta(days=5),
        })

    def _slug(self, record):
        return self.env['ir.http']._slug(record)

    def _ids(self, body):
        return [item['id'] for item in body['data']]

    # -- /blog/blogs -------------------------------------------------------

    def test_blogs_list(self):
        response, body = self.api('GET', '/blog/blogs')
        self.assertEqual(response.status_code, 200)
        entry = next((b for b in body['data'] if b['id'] == self.blog.id), None)
        self.assertTrue(entry, 'test blog missing from /blog/blogs')
        self.assertEqual(entry['name'], 'Odusite Test Blog')
        self.assertEqual(entry['subtitle'], 'All about testing')
        self.assertEqual(entry['slug'], self._slug(self.blog))
        # Only the 2 published, past-dated posts count.
        self.assertEqual(entry['post_count'], 2)

    # -- /blog/posts list ----------------------------------------------------

    def test_posts_publish_gate(self):
        response, body = self.api('GET', f'/blog/posts?blog={self.blog.id}')
        self.assertEqual(response.status_code, 200)
        # Newest first (published_desc default); unpublished and future-dated
        # posts are excluded.
        self.assertEqual(self._ids(body), [self.post_new.id, self.post_old.id])
        self.assertEqual(body['meta']['total'], 2)
        item = body['data'][0]
        for key in ('id', 'slug', 'name', 'subtitle', 'teaser', 'cover',
                    'author', 'tags', 'post_date', 'blog'):
            self.assertIn(key, item)
        self.assertEqual(item['blog']['id'], self.blog.id)
        self.assertIn('name', item['author'])
        self.assertIn({'id': self.tag_filter.id, 'slug': self._slug(self.tag_filter),
                       'name': self.tag_filter.name}, item['tags'])

    def test_posts_filter_tag(self):
        response, body = self.api('GET', f'/blog/posts?tag={self.tag_filter.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._ids(body), [self.post_new.id])

        response, body = self.api('GET', f'/blog/posts?tag={self._slug(self.tag_filter)}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._ids(body), [self.post_new.id])

    def test_posts_filter_search(self):
        response, body = self.api('GET', '/blog/posts?search=Zanzibar')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._ids(body), [self.post_old.id])

    def test_posts_filter_dates(self):
        pivot = (fields.Datetime.now() - timedelta(days=5)).date().isoformat()
        response, body = self.api(
            'GET', f'/blog/posts?blog={self.blog.id}&date_from={pivot}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._ids(body), [self.post_new.id])

        response, body = self.api(
            'GET', f'/blog/posts?blog={self.blog.id}&date_to={pivot}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._ids(body), [self.post_old.id])

        response, body = self.api(
            'GET', f'/blog/posts?blog={self.blog.id}&date_from=not-a-date')
        self.assert_api_error(response, body, 400, 'bad_request')

    def test_posts_bad_order(self):
        response, body = self.api('GET', '/blog/posts?order=hacker')
        self.assert_api_error(response, body, 400, 'bad_request')
        self.assertEqual(body['error']['details']['allowed'],
                         ['name', 'published_desc', 'visits'])

    def test_posts_pagination(self):
        response, body = self.api('GET', f'/blog/posts?blog={self.blog.id}&limit=1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._ids(body), [self.post_new.id])
        self.assertEqual(body['meta'],
                         {'total': 2, 'page': 1, 'limit': 1, 'pages': 2})

        response, body = self.api('GET', f'/blog/posts?blog={self.blog.id}&limit=1&page=2')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._ids(body), [self.post_old.id])
        self.assertEqual(body['meta']['page'], 2)

    # -- /blog/posts/<ref> detail --------------------------------------------

    def test_post_detail_by_id(self):
        response, body = self.api('GET', f'/blog/posts/{self.post_new.id}')
        self.assertEqual(response.status_code, 200)
        data = body['data']
        self.assertEqual(data['id'], self.post_new.id)
        self.assertIn('New post content body', data['content'])
        self.assertEqual(
            set(data['seo']), {'title', 'description', 'keywords', 'og_image'})
        self.assertEqual(data['seo']['title'], self.post_new.name)
        self.assertIsInstance(data['visits'], int)
        # prev/next inside the same blog, published only.
        self.assertEqual(data['prev']['id'], self.post_old.id)
        self.assertIsNone(data['next'])
        # Related by shared tag.
        self.assertEqual([p['id'] for p in data['related']], [self.post_old.id])

    def test_post_detail_prev_next_consistency(self):
        response, body = self.api('GET', f'/blog/posts/{self.post_old.id}')
        self.assertEqual(response.status_code, 200)
        data = body['data']
        self.assertIsNone(data['prev'])
        self.assertEqual(data['next']['id'], self.post_new.id)
        self.assertEqual(data['next']['slug'], self._slug(self.post_new))
        # Symmetric with detail(post_new).prev == post_old.
        self.assertEqual([p['id'] for p in data['related']], [self.post_new.id])

    def test_post_detail_by_slug(self):
        response, body = self.api('GET', f'/blog/posts/{self._slug(self.post_old)}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body['data']['id'], self.post_old.id)
        self.assertIn('Old post content body', body['data']['content'])

    def test_post_detail_increments_visits(self):
        self.post_old.invalidate_recordset(['visits'])
        before = self.post_old.visits
        response, body = self.api('GET', f'/blog/posts/{self.post_old.id}')
        self.assertEqual(response.status_code, 200)
        # The serialized payload carries the pre-increment counter.
        self.assertEqual(body['data']['visits'], before)
        # Non-blocking SQL write-through: re-read from the database.
        self.post_old.invalidate_recordset(['visits'])
        self.assertEqual(self.post_old.visits, before + 1)

    def test_post_detail_not_found(self):
        response, body = self.api('GET', f'/blog/posts/{self.post_unpublished.id}')
        self.assert_api_error(response, body, 404, 'not_found')

        response, body = self.api('GET', f'/blog/posts/{self.post_future.id}')
        self.assert_api_error(response, body, 404, 'not_found')

        response, body = self.api('GET', '/blog/posts/99999999')
        self.assert_api_error(response, body, 404, 'not_found')

        response, body = self.api('GET', '/blog/posts/not-a-slug')
        self.assert_api_error(response, body, 404, 'not_found')

    # -- /blog/tags ------------------------------------------------------------

    def test_blog_tags_endpoint(self):
        response, body = self.api('GET', '/blog/tags')
        self.assertEqual(response.status_code, 200)
        by_id = {tag['id']: tag for tag in body['data']}
        self.assertIn(self.tag_filter.id, by_id)
        self.assertIn(self.tag_shared.id, by_id)
        entry = by_id[self.tag_filter.id]
        self.assertEqual(entry['name'], self.tag_filter.name)
        self.assertEqual(entry['slug'], self._slug(self.tag_filter))
        self.assertIsNone(entry['category'])
        # Counts only cover published, past-dated posts.
        self.assertEqual(entry['post_count'], 1)
        self.assertEqual(by_id[self.tag_shared.id]['post_count'], 2)
