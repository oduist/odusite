"""boto3 S3/R2 client + low-level object operations for odusite_s3.

Everything that touches boto3 lives here so the rest of the addon has no hard
import on the optional dependency. boto3 is imported lazily; the manifest
``external_dependencies`` makes Odoo warn when it is missing.

The client is cached on the registry, keyed by the credentials tuple, so a
boto3 session is reused across requests (rebuilt automatically when the
settings change). S3Mock / Cloudflare R2 need path-style addressing and SigV4.
"""

import logging

from odoo import _
from odoo.exceptions import UserError
from odoo.tools import str2bool

_logger = logging.getLogger(__name__)

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # pragma: no cover - guarded by external_dependencies
    boto3 = None
    Config = None
    BotoCoreError = ClientError = Exception

DEFAULT_URL_EXPIRY = 900
# boto3 error codes that mean "the object simply is not there" -> read fallback.
_MISSING_CODES = ('NoSuchKey', 'NoSuchBucket', '404', 'NotFound')


def read_config(env):
    """Return the parsed ``odusite.s3.*`` configuration (params are ormcached)."""
    get = env['ir.config_parameter'].sudo().get_param
    try:
        url_expiry = int(get('odusite.s3.url_expiry') or 0) or DEFAULT_URL_EXPIRY
    except (TypeError, ValueError):
        url_expiry = DEFAULT_URL_EXPIRY
    return {
        'enabled': str2bool(get('odusite.s3.enabled') or 'False', False),
        'endpoint_url': (get('odusite.s3.endpoint_url') or '').strip(),
        'region': (get('odusite.s3.region') or '').strip(),
        'bucket': (get('odusite.s3.bucket') or '').strip(),
        'access_key': (get('odusite.s3.access_key') or '').strip(),
        'secret_key': (get('odusite.s3.secret_key') or '').strip(),
        'public_base_url': (get('odusite.s3.public_base_url') or '').strip().rstrip('/'),
        'url_expiry': url_expiry,
    }


def make_client(endpoint_url, region, access_key, secret_key):
    """Build a boto3 S3 client (uncached). Path-style + SigV4 for R2/S3Mock."""
    if boto3 is None:
        raise UserError(_(
            "The Python package 'boto3' is required for S3 offload but is not "
            "installed on the Odoo server."))
    return boto3.client(
        's3',
        endpoint_url=endpoint_url or None,
        aws_access_key_id=access_key or None,
        aws_secret_access_key=secret_key or None,
        region_name=region or None,
        config=Config(s3={'addressing_style': 'path'}, signature_version='s3v4'),
    )


def get_client(env):
    """Return a ``(client, cfg)`` pair, caching the client on the registry."""
    cfg = read_config(env)
    key = (cfg['endpoint_url'], cfg['region'], cfg['bucket'],
           cfg['access_key'], cfg['secret_key'])
    registry = env.registry
    cached = getattr(registry, '_odusite_s3_client', None)
    if cached is not None and cached[0] == key:
        return cached[1], cfg
    client = make_client(cfg['endpoint_url'], cfg['region'],
                         cfg['access_key'], cfg['secret_key'])
    registry._odusite_s3_client = (key, client)
    return client, cfg


# -- low level object operations -----------------------------------------

def get_object(env, key):
    """Return the object bytes, or ``None`` when the key is absent/unreadable."""
    client, cfg = get_client(env)
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
    client, cfg = get_client(env)
    try:
        client.head_object(Bucket=cfg['bucket'], Key=key)
        return True
    except (ClientError, BotoCoreError):
        return False


def put_object(env, key, data):
    client, cfg = get_client(env)
    client.put_object(Bucket=cfg['bucket'], Key=key, Body=data)


def delete_object(env, key):
    client, cfg = get_client(env)
    client.delete_object(Bucket=cfg['bucket'], Key=key)


def presigned_get(env, key, expiry):
    client, cfg = get_client(env)
    return client.generate_presigned_url(
        'get_object',
        Params={'Bucket': cfg['bucket'], 'Key': key},
        ExpiresIn=int(expiry or DEFAULT_URL_EXPIRY),
    )
