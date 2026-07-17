{
    'name': 'Odusite Forum',
    'summary': 'Headless REST API for the website forum (Odusite)',
    'description': """
Odusite API for forums (website_forum):
- public read endpoints: forums, posts (questions), tags, user profiles
- JWT actions: ask, answer, edit/delete, vote, accept, comment, favourite
- karma requirements enforced by the stock forum model methods and mapped
  to 403 karma_required API errors
- sitemap entries + cache-invalidation webhooks for forum.post / forum.forum
""",
    'category': 'Website',
    'version': '19.0.1.0.0',
    'author': 'Oduist OÜ',
    'license': 'Other OSI approved licence',
    'depends': ['odusite_base', 'odusite_portal', 'website_forum'],
    'installable': True,
}
