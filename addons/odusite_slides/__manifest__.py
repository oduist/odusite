{
    'name': 'Odusite eLearning',
    'summary': 'Headless REST API for eLearning courses (Odusite)',
    'description': """
Odusite API for eLearning (website_slides):
- GET /odusite/v1/courses (published, visible slide.channel)
- GET /odusite/v1/courses/<id_or_slug> (detail with categorized curriculum)
- POST /odusite/v1/courses/<id>/join (public-enroll courses, JWT)
- GET /odusite/v1/courses/<id>/slides/<slide_id> (content, video embed)
- GET /odusite/v1/courses/<id>/slides/<slide_id>/download (binary stream)
- POST /odusite/v1/courses/<id>/slides/<slide_id>/complete (JWT member)
- GET/POST /odusite/v1/courses/<id>/slides/<slide_id>/quiz (stock quiz logic)
- sitemap entries + cache-invalidation webhooks for slide.channel / slide.slide
""",
    'category': 'Website',
    'version': '19.0.1.0.0',
    'author': 'Oduist OÜ',
    'license': 'MIT',
    'depends': ['odusite_base', 'odusite_portal', 'website_slides'],
    'installable': True,
}
