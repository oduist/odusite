{
    'name': 'Odusite Mass Mailing',
    'summary': 'Headless newsletter subscription for mailing lists',
    'description': """
Odusite endpoints for website_mass_mailing:
- /odusite/v1/newsletter/subscribe -> mailing.contact + mailing.subscription
  (same semantics as the upstream /website_mass_mailing/subscribe controller,
  honeypot instead of recaptcha)
- /odusite/v1/newsletter/lists -> public mailing lists
""",
    'category': 'Website',
    'version': '19.0.1.0.0',
    'author': 'Oduist OÜ',
    'license': 'MIT',
    'depends': ['odusite_base', 'website_mass_mailing'],
    'installable': True,
}
