"""boto3 S3/R2 client + low-level object operations for odusite_s3.

Everything that touches boto3 lives here so the rest of the addon has no hard
import on the optional dependency (boto3 is imported lazily; the manifest
``external_dependencies`` makes Odoo warn when it is missing).

Connection settings are resolved with this precedence (documented in
specs/modules/odusite_s3.md and docs/admin/s3.md):

    1. odoo.conf ``[options]``  ->  ``odusite_s3_<name>``
    2. environment variable     ->  ``ODUSITE_S3_<NAME>``
    3. database system param    ->  ``odusite.s3.<name>``

Secrets can therefore be supplied out-of-band (conf/env, recommended for
production hardening) while the Settings UI (DB params) stays available for
quick testing — conf/env always win. boto3 clients are cached per-process,
keyed by the resolved settings, so the underlying HTTP connection pool is
reused across requests (a client is transparently rebuilt when settings change,
or when a *public* endpoint is requested for browser-facing presigned URLs).
The client is intentionally configured for path-style + SigV4 addressing, which
S3Mock, MinIO and Cloudflare R2 all require.
"""

import logging
import os
import threading

from odoo import _
from odoo.exceptions import UserError
from odoo.tools import config, str2bool

_logger = logging.getLogger(__name__)

try:
    import boto3
    from botocore.config import Config as BotoConfig
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # pragma: no cover - guarded by external_dependencies
    boto3 = None
    BotoConfig = None
    BotoCoreError = ClientError = Exception

DEFAULT_URL_EXPIRY = 900
# max_pool_connections must be >= the migration worker count so concurrent
# uploads are not serialised by the botocore HTTP pool (workers are capped at 64).
DEFAULT_MAX_POOL = 64
# boto3 error codes that mean "the object simply is not there" -> read fallback.
_MISSING_CODES = ('NoSuchKey', 'NoSuchBucket', '404', 'NotFound')

# connection settings resolved through conf/env/DB (see module docstring)
_CONN_KEYS = (
    'endpoint_url', 'public_endpoint_url', 'public_base_url',
    'region', 'bucket', 'access_key', 'secret_key',
)

# per-process cache: settings-signature -> boto3 client
_clients = {}
_clients_lock = threading.Lock()


def _resolve(env, name):
    """Resolve one connection setting following the conf/env/DB precedence."""
    conf_key = 'odusite_s3_' + name
    value = config.get(conf_key)
    if value:
        return str(value).strip()
    value = os.environ.get(conf_key.upper())
    if value:
        return value.strip()
    value = env['ir.config_parameter'].sudo().get_param('odusite.s3.' + name)
    return (value or '').strip()


def read_config(env):
    """Return the merged ``odusite.s3.*`` configuration as a dict."""
    get = env['ir.config_parameter'].sudo().get_param
    try:
        url_expiry = int(get('odusite.s3.url_expiry') or 0) or DEFAULT_URL_EXPIRY
    except (TypeError, ValueError):
        url_expiry = DEFAULT_URL_EXPIRY
    cfg = {name: _resolve(env, name) for name in _CONN_KEYS}
    cfg['endpoint_url'] = cfg['endpoint_url'].rstrip('/')
    cfg['public_endpoint_url'] = cfg['public_endpoint_url'].rstrip('/')
    cfg['public_base_url'] = cfg['public_base_url'].rstrip('/')
    cfg['enabled'] = str2bool(get('odusite.s3.enabled') or 'False', False)
    cfg['url_expiry'] = url_expiry
    return cfg


def has_boto3():
    return boto3 is not None


def is_configured(cfg):
    """True when boto3 is present and the mandatory credentials are set."""
    return bool(boto3 is not None and cfg.get('bucket')
                and cfg.get('access_key') and cfg.get('secret_key'))


def get_bucket(env, cfg=None):
    return (cfg or read_config(env)).get('bucket')


def make_client(endpoint_url, region, access_key, secret_key):
    """Build an *uncached* boto3 S3 client (used by the Test-connection button)."""
    if boto3 is None:
        raise UserError(_(
            "The Python package 'boto3' is required for S3 offload but is not "
            "installed on the Odoo server."))
    s3_cfg = {}
    if endpoint_url:
        s3_cfg['addressing_style'] = 'path'
    return boto3.client(
        's3',
        endpoint_url=(endpoint_url or None),
        aws_access_key_id=(access_key or None),
        aws_secret_access_key=(secret_key or None),
        region_name=(region or None),
        config=BotoConfig(signature_version='s3v4', s3=s3_cfg,
                          max_pool_connections=DEFAULT_MAX_POOL),
    )


def get_client(env, public=False, cfg=None):
    """Return a cached boto3 S3 client.

    :param public: when True use ``public_endpoint_url`` (if set) so generated
                   presigned URLs point at a host reachable by end-user browsers.
    """
    if boto3 is None:
        raise UserError(_(
            "The Python package 'boto3' is required for S3 offload but is not "
            "installed on the Odoo server."))
    cfg = cfg or read_config(env)
    endpoint_url = cfg.get('endpoint_url')
    if public and cfg.get('public_endpoint_url'):
        endpoint_url = cfg.get('public_endpoint_url')
    signature = (
        endpoint_url,
        cfg.get('access_key'),
        cfg.get('secret_key'),
        cfg.get('region'),
    )
    client = _clients.get(signature)
    if client is None:
        with _clients_lock:
            client = _clients.get(signature)
            if client is None:
                client = make_client(
                    endpoint_url, cfg.get('region'),
                    cfg.get('access_key'), cfg.get('secret_key'))
                _clients[signature] = client
    return client


# -- low level object operations -----------------------------------------

def upload_dedup(client, bucket, key, data, content_type=None):
    """Upload ``data`` to ``key`` unless the object already exists (dedup).

    boto3 clients are thread-safe, so this helper may be called concurrently
    from migration worker threads with an explicit (pre-fetched) client.
    Returns True when it actually uploaded.
    """
    try:
        client.head_object(Bucket=bucket, Key=key)
        return False  # already present -> skip re-upload
    except Exception:  # noqa: BLE001 - any miss/transient -> attempt the put
        pass
    extra = {'ContentType': content_type} if content_type else {}
    client.put_object(Bucket=bucket, Key=key, Body=data, **extra)
    return True


def get_object(env, key):
    """Return the object bytes, or ``None`` when the key is absent/unreadable."""
    cfg = read_config(env)
    client = get_client(env, cfg=cfg)
    try:
        resp = client.get_object(Bucket=cfg['bucket'], Key=key)
        return resp['Body'].read()
    except ClientError as exc:
        code = exc.response.get('Error', {}).get('Code')
        if code in _MISSING_CODES:
            return None
        _logger.warning("odusite_s3: get_object %s failed: %s", key, exc)
        return None
    except BotoCoreError as exc:
        _logger.warning("odusite_s3: get_object %s failed: %s", key, exc)
        return None


def head_object(env, key):
    """True when the object exists (used for dedup and idempotent migration)."""
    cfg = read_config(env)
    client = get_client(env, cfg=cfg)
    try:
        client.head_object(Bucket=cfg['bucket'], Key=key)
        return True
    except (ClientError, BotoCoreError):
        return False


def put_object(env, key, data, content_type=None):
    cfg = read_config(env)
    client = get_client(env, cfg=cfg)
    extra = {'ContentType': content_type} if content_type else {}
    client.put_object(Bucket=cfg['bucket'], Key=key, Body=data, **extra)


def delete_object(env, key):
    cfg = read_config(env)
    client = get_client(env, cfg=cfg)
    client.delete_object(Bucket=cfg['bucket'], Key=key)


def presigned_get(env, key, expiry=None, download=False, filename=None):
    """Generate a short-lived presigned GET URL (via the *public* client)."""
    cfg = read_config(env)
    client = get_client(env, public=True, cfg=cfg)
    params = {'Bucket': cfg['bucket'], 'Key': key}
    if download and filename:
        params['ResponseContentDisposition'] = (
            'attachment; filename="%s"' % filename.replace('"', ''))
    return client.generate_presigned_url(
        'get_object',
        Params=params,
        ExpiresIn=int(expiry or cfg['url_expiry'] or DEFAULT_URL_EXPIRY),
    )
