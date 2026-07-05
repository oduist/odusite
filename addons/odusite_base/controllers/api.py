"""Odusite API core: token gate, JWT resolution, JSON envelope, pagination.

Every odusite_* controller must declare routes with :func:`odusite_route`
instead of a raw ``@http.route`` (see specs/02-api-conventions.md).

Handler conventions:
- accept ``**kwargs`` (query params and JSON body keys are merged into kwargs;
  path params take precedence over body keys);
- return a dict/list (wrapped as ``{"data": ...}``), a ``(data, meta)`` tuple
  (wrapped as ``{"data": ..., "meta": ...}``), ``None`` (204), or a
  werkzeug/odoo Response (passed through, e.g. for binary streams);
- raise :class:`ApiError` for explicit API errors.
"""

import functools
import json
import logging

import werkzeug.exceptions
import werkzeug.wrappers

from odoo import http
from odoo.exceptions import AccessDenied, AccessError, MissingError, UserError, ValidationError
from odoo.http import request
from odoo.tools import consteq

from ..lib import jwt as jwt_lib

_logger = logging.getLogger(__name__)

API_PREFIX = '/odusite/v1'
DEFAULT_LIMIT = 20
MAX_LIMIT = 100


class ApiError(Exception):
    def __init__(self, status, code, message, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}


def get_param(name):
    return request.env['ir.config_parameter'].sudo().get_param(name)


def error_response(status, code, message, details=None):
    return request.make_json_response(
        {'error': {'code': code, 'message': message, 'details': details or {}}},
        status=status,
    )


def _check_site_token():
    expected = get_param('odusite.token')
    provided = request.httprequest.headers.get('X-Odusite-Token')
    if not expected or not provided or not consteq(expected, provided):
        raise ApiError(401, 'unauthorized', 'Missing or invalid X-Odusite-Token header.')


def _resolve_website():
    """Bind the configured website into the request so website-aware model
    code (pricelists, published domains, image_url) behaves as on a stock
    website request."""
    website = None
    website_id = get_param('odusite.website_id')
    if website_id:
        try:
            website = request.env['website'].sudo().browse(int(website_id)).exists()
        except ValueError:
            website = None
    if not website:
        website = request.env['website'].sudo().search([], limit=1, order='sequence, id')
    if not website:
        raise ApiError(500, 'internal', 'No website configured in Odoo.')
    request.website = website
    request.update_context(website_id=website.id)
    _bind_frontend_lazies()
    return website


def _bind_frontend_lazies():
    """Mirror the request attributes website_sale's ir.http binds on website
    routes (odusite routes are not website-routed). Upstream helpers such as
    portal's address validation read ``request.cart`` when website_sale is
    installed; give them safe empty defaults. odusite_sale rebinds them with
    real values where pricing matters."""
    env = request.env
    if 'sale.order' in env and not hasattr(request, 'cart'):
        request.cart = env['sale.order'].sudo().browse()
    if 'product.pricelist' in env and not hasattr(request, 'pricelist'):
        request.pricelist = env['product.pricelist'].sudo().browse()
    if 'account.fiscal.position' in env and not hasattr(request, 'fiscal_position'):
        request.fiscal_position = env['account.fiscal.position'].sudo().browse()


def _activate_lang(website):
    lang = request.httprequest.args.get('lang')
    if not lang:
        header = request.httprequest.headers.get('Accept-Language', '')
        lang = header.split(',')[0].split(';')[0].strip().replace('-', '_') if header else None
    if not lang:
        return
    codes = website.language_ids.mapped('code') or [website.default_lang_id.code]
    match = next(
        (code for code in codes
         if code == lang or code.split('_')[0] == lang.split('_')[0]),
        None,
    )
    if match:
        request.update_context(lang=match)


def _resolve_jwt(auth_user):
    """Resolve the optional Bearer JWT.

    On public endpoints (auth_user=False) an invalid/expired token degrades to
    anonymous instead of failing — the frontend may carry a stale cookie while
    calling e.g. /auth/refresh or browsing the catalog.
    """
    try:
        return _resolve_jwt_strict(auth_user)
    except ApiError:
        if auth_user:
            raise
        return None


def _resolve_jwt_strict(auth_user):
    authorization = request.httprequest.headers.get('Authorization', '')
    uid = None
    if authorization.startswith('Bearer '):
        token = authorization[7:].strip()
        secret = get_param('odusite.jwt_secret')
        if not secret:
            raise ApiError(500, 'internal', 'JWT secret is not configured.')
        try:
            payload = jwt_lib.verify(token, secret)
        except jwt_lib.ExpiredToken:
            raise ApiError(401, 'jwt_expired', 'Access token has expired.')
        except jwt_lib.InvalidToken:
            raise ApiError(401, 'invalid_jwt', 'Invalid access token.')
        if payload.get('typ') != 'access':
            raise ApiError(401, 'invalid_jwt', 'Invalid token type.')
        try:
            uid = int(payload.get('sub', 0))
        except (TypeError, ValueError):
            raise ApiError(401, 'invalid_jwt', 'Invalid subject claim.')
        user = request.env['res.users'].sudo().browse(uid).exists()
        if not user or not user.active:
            raise ApiError(401, 'invalid_jwt', 'Unknown or inactive user.')
        request.update_env(user=uid)
    if auth_user and not uid:
        raise ApiError(401, 'unauthorized', 'This endpoint requires a Bearer access token.')
    return uid


def _parse_body():
    if request.httprequest.method not in ('POST', 'PUT', 'PATCH', 'DELETE'):
        return {}
    if request.httprequest.mimetype != 'application/json':
        return {}
    raw = request.httprequest.get_data()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        raise ApiError(400, 'bad_request', 'Invalid JSON body.')
    if not isinstance(data, dict):
        raise ApiError(400, 'bad_request', 'JSON body must be an object.')
    return data


def _make_response(result):
    if isinstance(result, werkzeug.wrappers.Response):
        return result
    if result is None:
        return request.make_response('', status=204)
    if isinstance(result, tuple) and len(result) == 2:
        data, meta = result
        return request.make_json_response({'data': data, 'meta': meta})
    return request.make_json_response({'data': result})


def odusite_route(path, methods, auth_user=False, **routing):
    """Declare an Odusite API route.

    :param path: full route path (use :data:`API_PREFIX`).
    :param methods: explicit HTTP methods, e.g. ``['GET']``.
    :param auth_user: when True the route requires a valid Bearer JWT.
    """
    routing.setdefault('type', 'http')
    routing.setdefault('auth', 'public')
    routing.setdefault('csrf', False)
    routing.setdefault('save_session', False)
    routing['methods'] = methods

    def decorator(func):
        @http.route(path, **routing)
        @functools.wraps(func)
        def wrapper(*args, **params):
            try:
                _check_site_token()
                website = _resolve_website()
                _activate_lang(website)
                _resolve_jwt(auth_user)
                body = _parse_body()
                for key, value in body.items():
                    params.setdefault(key, value)
                return _make_response(func(*args, **params))
            except werkzeug.exceptions.HTTPException:
                raise
            except Exception as exc:
                # Error responses must never commit partial writes (e.g. a
                # forum post INSERTed before its karma check raised).
                _rollback_quietly()
                return _exception_response(exc, path)
        return wrapper
    return decorator


def _rollback_quietly():
    try:
        request.env.cr.rollback()
    except Exception:  # pragma: no cover - cursor already closed/broken
        _logger.exception('Rollback failed in odusite endpoint')


def _exception_response(exc, path):
    if isinstance(exc, ApiError):
        return error_response(exc.status, exc.code, exc.message, exc.details)
    if isinstance(exc, ValidationError):
        return error_response(422, 'validation_error', _exc_message(exc))
    if isinstance(exc, AccessDenied):
        return error_response(401, 'unauthorized', 'Access denied.')
    if isinstance(exc, AccessError):
        return error_response(403, 'forbidden', 'You are not allowed to access this resource.')
    if isinstance(exc, MissingError):
        return error_response(404, 'not_found', 'The requested record does not exist.')
    if isinstance(exc, UserError):
        return error_response(400, 'bad_request', _exc_message(exc))
    _logger.exception('Unhandled error in odusite endpoint %s', path)
    return error_response(500, 'internal', 'Internal server error.')


def _exc_message(exc):
    return str(exc.args[0]) if exc.args else str(exc)


def parse_pagination(params, order_whitelist=None, default_order=None, max_limit=MAX_LIMIT):
    """Parse page/limit/order params.

    :param order_whitelist: mapping of public order key -> ORM order clause.
    :return: (page, limit, offset, order_clause)
    """
    try:
        page = max(1, int(params.get('page', 1)))
        limit = int(params.get('limit', DEFAULT_LIMIT))
    except (TypeError, ValueError):
        raise ApiError(400, 'bad_request', 'Invalid pagination parameters.')
    limit = max(1, min(limit, max_limit))

    order = None
    order_key = params.get('order') or default_order
    if order_whitelist and order_key:
        if order_key not in order_whitelist:
            raise ApiError(400, 'bad_request', f'Unsupported order key: {order_key}',
                           {'allowed': sorted(order_whitelist)})
        order = order_whitelist[order_key]
    return page, limit, (page - 1) * limit, order


def list_meta(total, page, limit, **extra):
    meta = {
        'total': total,
        'page': page,
        'limit': limit,
        'pages': (total + limit - 1) // limit if limit else 0,
    }
    meta.update(extra)
    return meta


def get_cart_binding(required=False):
    """Parse the ``X-Odusite-Cart: <id>:<token>`` header (see ADR-007)."""
    header = request.httprequest.headers.get('X-Odusite-Cart', '')
    if not header:
        if required:
            raise ApiError(400, 'bad_request', 'Missing X-Odusite-Cart header.')
        return None
    cart_id, _, token = header.partition(':')
    if not cart_id.isdigit() or not token:
        raise ApiError(400, 'bad_request', 'Malformed X-Odusite-Cart header.')
    return int(cart_id), token
