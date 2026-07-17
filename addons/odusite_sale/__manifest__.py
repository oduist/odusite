{
    'name': 'Odusite Sale',
    'summary': 'Headless REST API for the eCommerce: catalog, cart, checkout, portal orders',
    'description': """
Odusite eCommerce API (see specs/modules/odusite_sale.md):
- Catalog: categories tree, product listing with filters/facets, product
  detail, combination info endpoint
- Stateless cart (ADR-007): draft sale.order addressed by id + access_token
  through the X-Odusite-Cart header
- Checkout: state machine, guest/portal addresses, delivery method selection
- Portal orders: list, detail, accept (sign), decline, PDF download
- Sitemap/webhook/counter/chatter hooks for the Odusite core
""",
    'category': 'Website',
    'version': '19.0.1.0.0',
    'author': 'Oduist OÜ',
    'license': 'Other OSI approved licence',
    'depends': ['odusite_base', 'odusite_portal', 'website_sale'],
    'data': [],
    'installable': True,
}
