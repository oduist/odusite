{
    'name': 'Odusite Portal',
    'summary': 'Headless JWT authentication and portal core for the Odusite frontend',
    'description': """
Odusite portal core (see specs/03-auth.md and specs/modules/odusite_portal.md):
- JWT authentication: /odusite/v1/auth/* (login, refresh, logout, signup with
  email double opt-in, confirm/resend, password forgot/reset), rotating
  refresh tokens stored hashed in Odoo
- Portal profile: /odusite/v1/me (profile, password, addresses, counters,
  sessions)
- Generic portal chatter: /odusite/v1/chatter/* (messages, attachments)
- auth_signup email templates overridden so links point to odusite.site_url
""",
    'category': 'Website',
    'version': '19.0.1.0.0',
    'author': 'Oduist OÜ',
    'license': 'Other OSI approved licence',
    'depends': ['odusite_base', 'portal', 'auth_signup'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'data/mail_template_data.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
}
