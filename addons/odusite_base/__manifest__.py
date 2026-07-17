{
    'name': 'Odusite Base',
    'summary': 'Headless REST API core for the Odusite Astro frontend',
    'description': """
Core of the Odusite headless integration:
- X-Odusite-Token gate and the odusite_route() controller helper
- JWT utilities (HS256, stdlib only)
- JSON envelope, pagination, serialization helpers
- Cache-invalidation webhook queue (Odoo -> site)
- Site-wide endpoints: /site, /menus, /sitemap, /redirects, /countries, /health,
  /search (unified website search)
""",
    'category': 'Website',
    'version': '19.0.1.0.0',
    'author': 'Oduist OÜ',
    'license': 'Other OSI approved licence',
    'depends': ['website'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/res_config_settings_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
}
