{
    'name': 'Odusite Partner',
    'summary': 'Headless REST API for the public partner directory',
    'description': """
Odusite endpoints for website_partner:
- /odusite/v1/partners (published partners, country/grade/tag facets)
- /odusite/v1/partners/<id_or_slug> detail
Grades/references require website_crm_partner_assign, tags require
website_customer; both are detected at runtime and optional.
""",
    'category': 'Website',
    'version': '19.0.1.0.0',
    'author': 'Oduist OÜ',
    'license': 'MIT',
    'depends': ['odusite_base', 'website_partner'],
    'installable': True,
}
