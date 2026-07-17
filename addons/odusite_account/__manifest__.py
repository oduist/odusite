{
    'name': 'Odusite Account',
    'summary': 'Portal invoices API for the Odusite frontend',
    'description': """
Customer invoices for the Odusite portal (see specs/modules/odusite_account.md):
- GET /odusite/v1/my/invoices: paginated posted customer invoices (JWT)
- GET /odusite/v1/my/invoices/<id>: invoice detail with lines and totals
- GET /odusite/v1/my/invoices/<id>/pdf: legal invoice PDF stream
- portal counter 'invoices' and chatter whitelist for account.move

Payment goes through odusite_payment with document "invoice:<id>".
""",
    'category': 'Website',
    'version': '19.0.1.0.0',
    'author': 'Oduist OÜ',
    'license': 'MIT',
    'depends': ['odusite_base', 'odusite_portal', 'odusite_payment', 'account'],
    'installable': True,
}
