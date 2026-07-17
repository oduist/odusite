{
    'name': 'Odusite HR Recruitment',
    'summary': 'Headless REST API for the jobs page and applications',
    'description': """
Odusite endpoints for website_hr_recruitment:
- /odusite/v1/jobs (published jobs with department/country/type facets)
- /odusite/v1/jobs/<id_or_slug> detail
- /odusite/v1/jobs/<id>/apply multipart application with CV upload
""",
    'category': 'Website',
    'version': '19.0.1.0.0',
    'author': 'Oduist OÜ',
    'license': 'Other OSI approved licence',
    'depends': ['odusite_base', 'website_hr_recruitment'],
    'installable': True,
}
