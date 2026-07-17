{
    'name': 'Odusite Blog',
    'summary': 'Headless REST API for the website blog',
    'description': """
Odusite endpoints for website_blog:
- /odusite/v1/blog/blogs, /odusite/v1/blog/posts, /odusite/v1/blog/tags
- Sitemap entries and cache-invalidation webhooks for blog content
""",
    'category': 'Website',
    'version': '19.0.1.0.0',
    'author': 'Oduist OÜ',
    'license': 'MIT',
    'depends': ['odusite_base', 'website_blog'],
    'installable': True,
}
