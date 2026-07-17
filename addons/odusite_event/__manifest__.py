{
    'name': 'Odusite Events',
    'summary': 'Headless REST API for website events (Odusite)',
    'description': """
Odusite API for events (website_event):
- GET /odusite/v1/events (published, visible events; tag/country/period filters)
- GET /odusite/v1/events/<id_or_slug> (detail with tickets, seats, seo)
- POST /odusite/v1/events/<id>/register (free tickets only, phase 1)
- GET /odusite/v1/events/<id>/ics
- sitemap entries + cache-invalidation webhooks for event.event / event.tag
""",
    'category': 'Website',
    'version': '19.0.1.0.0',
    'author': 'Oduist OÜ',
    'license': 'MIT',
    'depends': ['odusite_base', 'website_event'],
    'installable': True,
}
