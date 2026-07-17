{
    'name': 'Odusite CRM',
    'summary': 'Headless website forms creating CRM leads',
    'description': """
Odusite endpoints for website_crm:
- /odusite/v1/forms/contact -> crm.lead (UTM mapping, website sales team)
- /odusite/v1/forms/generic/<model> whitelisted generic form endpoint
- Honeypot rejection and per-IP throttle as defense in depth
""",
    'category': 'Website',
    'version': '19.0.1.0.0',
    'author': 'Oduist OÜ',
    'license': 'MIT',
    'depends': ['odusite_base', 'website_crm'],
    'installable': True,
}
