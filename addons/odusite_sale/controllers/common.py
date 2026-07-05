"""Shared request bindings and serializers for the odusite_sale controllers.

website_sale's ``ir.http._frontend_pre_dispatch`` binds lazy ``request.cart``,
``request.pricelist`` and ``request.fiscal_position`` on website requests,
backed by the Odoo session. Odusite requests have no Odoo session (ADR-007):
the cart is addressed by the ``X-Odusite-Cart: <id>:<token>`` header, and the
pricelist / fiscal position are resolved per request from the JWT partner
(or the website public partner for guests). This module re-creates those
bindings so the stock website_sale model code (``_get_combination_info``,
``_get_sales_prices``, ``_cart_add``, ``_update_address``, ...) keeps working
unchanged.
"""

from odoo.http import request
from odoo.tools import consteq, lazy

from odoo.addons.odusite_base.controllers.api import ApiError, get_cart_binding
from odoo.addons.odusite_base.lib import serializers

#: Optional keys forwarded from ``_get_combination_info`` when
#: website_sale_stock (and friends) are installed.
COMBINATION_EXTRA_KEYS = (
    'is_storable',
    'allow_out_of_stock_order',
    'available_threshold',
    'free_qty',
    'cart_qty',
    'uom_name',
    'uom_rounding',
    'show_availability',
    'out_of_stock_message',
    'max_combo_quantity',
    'tax_disclaimer',
)


def pricing_partner():
    """Partner driving the pricing context: the JWT user's partner when
    authenticated, the website public partner otherwise."""
    user = request.env.user
    if user._is_public():
        return request.website.user_id.sudo().partner_id
    return user.partner_id


def _resolve_pricelist(website):
    """Session-less port of ``website._get_and_cache_current_pricelist()``."""
    ProductPricelistSudo = request.env['product.pricelist'].sudo()
    if not request.env['res.groups']._is_feature_enabled('product.group_product_pricelist'):
        return ProductPricelistSudo

    if cart_sudo := request.cart:
        return cart_sudo.pricelist_id.sudo()

    partner_sudo = pricing_partner().sudo().with_company(website.company_id)
    pricelist_sudo = partner_sudo.property_product_pricelist
    available_pricelists = website.get_pricelist_available()
    if available_pricelists and pricelist_sudo not in available_pricelists:
        pricelist_sudo = available_pricelists[0]
    return pricelist_sudo.sudo()


def _resolve_fiscal_position(website):
    """Session-less port of ``website._get_and_cache_current_fiscal_position()``.

    No GeoIP in v1: guests get the fiscal position matching the website
    company country, portal users the one matching their partner.
    """
    AccountFiscalPositionSudo = request.env['account.fiscal.position'].sudo()
    if cart_sudo := request.cart:
        return cart_sudo.fiscal_position_id.sudo()

    if request.env.user._is_public():
        dummy_partner = request.env['res.partner'].sudo().new({
            'country_id': website.company_id.country_id.id,
        })
        return AccountFiscalPositionSudo._get_fiscal_position(dummy_partner)
    return AccountFiscalPositionSudo._get_fiscal_position(request.env.user.partner_id)


def bind_pricing(cart_sudo=None):
    """Bind ``request.cart`` / ``request.pricelist`` / ``request.fiscal_position``
    exactly like website_sale's ``_frontend_pre_dispatch`` (lazy, sudoed)."""
    website = request.website
    request.cart = cart_sudo if cart_sudo is not None else request.env['sale.order'].sudo()
    request.pricelist = lazy(lambda: _resolve_pricelist(website))
    request.fiscal_position = lazy(lambda: _resolve_fiscal_position(website))
    if not hasattr(request, 'lang'):
        # http_routing only sets request.lang on frontend routes; portal's
        # _complete_address_values() reads request.lang.code.
        ResLang = request.env['res.lang']
        lang_code = request.env.context.get('lang')
        request.lang = (
            (lang_code and ResLang._get_data(code=lang_code))
            or ResLang._get_data(code=website.default_lang_id.code)
        )


def get_cart(required=True):
    """Resolve the cart bound by the X-Odusite-Cart header (ADR-007).

    Verifies the access token (consteq), the draft state and the website, and
    binds the pricing context on the request. Returns the sudoed sale.order,
    or None when the header is absent and ``required`` is False.
    """
    binding = get_cart_binding(required=required)
    if not binding:
        bind_pricing()
        return None
    cart_id, token = binding

    order_sudo = request.env['sale.order'].sudo().browse(cart_id).exists()
    if (
        not order_sudo
        or not order_sudo.access_token
        or not consteq(order_sudo.access_token, token)
        or order_sudo.website_id.id != request.website.id
    ):
        raise ApiError(404, 'not_found', 'Cart not found.')
    if order_sudo.state != 'draft':
        raise ApiError(409, 'conflict', 'The cart is no longer a draft order.',
                       {'state': order_sudo.state})
    # Mirror website._get_and_cache_current_cart(): a cart with an ongoing
    # payment must not be reused/mutated.
    if order_sudo.get_portal_last_transaction().state in ('pending', 'authorized', 'done'):
        raise ApiError(409, 'conflict', 'A payment is already registered on this cart.')

    bind_pricing(order_sudo)
    return order_sudo


def peek_cart():
    """Best-effort cart binding for catalog pricing: a missing or invalid
    header falls back to the guest pricing context instead of failing."""
    try:
        return get_cart(required=False)
    except ApiError:
        bind_pricing()
        return None


def amount(value, currency):
    """Round a monetary value with the currency's decimal places."""
    return round(value or 0.0, currency.decimal_places if currency else 2)


def serialize_amounts(order_sudo):
    currency = order_sudo.currency_id
    return {
        'untaxed': amount(order_sudo.amount_untaxed, currency),
        'tax': amount(order_sudo.amount_tax, currency),
        'delivery': amount(order_sudo.amount_delivery, currency),
        'total': amount(order_sudo.amount_total, currency),
        'currency': currency.name,
    }


def serialize_cart_line(line):
    currency = line.currency_id
    product = line.product_id
    template = product.product_tmpl_id
    values = {
        'id': line.id,
        'product': {
            'id': product.id,
            'template_id': template.id,
            'slug': serializers.slug(template) if template else None,
            'name': line._get_line_header(),
            'image': serializers.image_url(product, 'image_128'),
        },
        'description': line._get_sale_order_line_multiline_description_variants() or '',
        'combination_name': line._get_combination_name() or '',
        'quantity': line._get_displayed_quantity(),
        'price_unit': amount(line._get_displayed_unit_price(), currency),
        'price_subtotal': amount(line.price_subtotal, currency),
        'price_total': amount(line.price_total, currency),
        'is_delivery': bool(line.is_delivery),
    }
    if 'is_reward_line' in line._fields:  # website_sale_loyalty installed
        values['is_reward'] = bool(line.is_reward_line)
    if line.shop_warning:
        values['warning'] = line.shop_warning
    return values


def serialize_cart(order_sudo):
    website = request.website
    return {
        'id': order_sudo.id,
        'cart_quantity': order_sudo.cart_quantity,
        'lines': [serialize_cart_line(line) for line in order_sudo.website_order_line],
        'amounts': serialize_amounts(order_sudo),
        'tax_mode': (
            'included' if website.show_line_subtotals_tax_selection == 'tax_included'
            else 'excluded'
        ),
    }


def serialize_combination_info(info, template):
    """JSON-safe projection of ``product.template._get_combination_info()``."""
    currency = info.get('currency') or request.website.currency_id
    product = None
    if info.get('product_id'):
        product = request.env['product.product'].sudo().browse(info['product_id'])

    if product and product.image_128:
        image = serializers.image_url(product, 'image_512')
    else:
        image = serializers.image_url(template.sudo()._get_image_holder(), 'image_512')

    values = {
        'product_id': info.get('product_id') or None,
        'product_template_id': info.get('product_template_id'),
        'display_name': info.get('display_name'),
        'is_combination_possible': info.get('is_combination_possible', True),
        'price': amount(info.get('price'), currency),
        'list_price': amount(info.get('list_price'), currency),
        'has_discounted_price': bool(info.get('has_discounted_price')),
        'prevent_zero_price_sale': bool(info.get('prevent_zero_price_sale')),
        'currency': currency.name,
        'image': image,
    }
    if info.get('compare_list_price'):
        values['compare_list_price'] = amount(info['compare_list_price'], currency)
    for key in COMBINATION_EXTRA_KEYS:
        if key in info:
            values[key] = info[key]
    return values
