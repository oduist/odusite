"""Storage tests against a live S3-compatible mock (adobe/s3mock or MinIO).

The whole class is skipped when boto3 is missing or the mock is unreachable, so
the suite stays green in environments without object storage.
"""

import unittest
import uuid

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.odusite_base.lib import serializers

S3_ENDPOINT = 'http://oduflow-svc-minio:9090'
S3_BUCKET = 'odusite-media'
S3_REGION = 'us-east-1'
S3_KEY = 'test'

# 1x1 transparent PNG (valid image for res.partner.image_1920)
PNG_1PX = (
    b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk'
    b'+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
)


@tagged('post_install', '-at_install')
class TestS3Storage(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            import boto3
            from botocore.config import Config
            from botocore.exceptions import BotoCoreError, ClientError
        except ImportError as exc:  # pragma: no cover
            raise unittest.SkipTest("boto3 not installed: %s" % exc)

        cls.ClientError = ClientError
        client = boto3.client(
            's3',
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=S3_KEY,
            aws_secret_access_key=S3_KEY,
            region_name=S3_REGION,
            config=Config(s3={'addressing_style': 'path'}, signature_version='s3v4'),
        )
        # connectivity probe: skip cleanly when the mock is unreachable
        try:
            client.list_buckets()
        except Exception as exc:  # noqa: BLE001
            raise unittest.SkipTest("S3 mock unreachable at %s: %s" % (S3_ENDPOINT, exc))
        # ensure the bucket exists
        try:
            client.head_bucket(Bucket=S3_BUCKET)
        except (ClientError, BotoCoreError):
            try:
                client.create_bucket(Bucket=S3_BUCKET)
            except (ClientError, BotoCoreError) as exc:
                raise unittest.SkipTest("cannot create bucket %s: %s" % (S3_BUCKET, exc))
        cls.s3_client = client

        icp = cls.env['ir.config_parameter'].sudo()
        icp.set_param('odusite.s3.enabled', 'True')
        icp.set_param('odusite.s3.endpoint_url', S3_ENDPOINT)
        icp.set_param('odusite.s3.region', S3_REGION)
        icp.set_param('odusite.s3.bucket', S3_BUCKET)
        icp.set_param('odusite.s3.access_key', S3_KEY)
        icp.set_param('odusite.s3.secret_key', S3_KEY)
        icp.set_param('odusite.s3.url_expiry', '900')
        # drop any cached boto3 client so the mock config is picked up
        if hasattr(cls.env.registry, '_odusite_s3_client'):
            del cls.env.registry._odusite_s3_client

        cls.Attachment = cls.env['ir.attachment']

    # -- helpers ---------------------------------------------------------

    def _object_bytes(self, key):
        return self.s3_client.get_object(Bucket=S3_BUCKET, Key=key)['Body'].read()

    # -- tests -----------------------------------------------------------

    def test_roundtrip(self):
        payload = b'odusite-s3-roundtrip-' + uuid.uuid4().hex.encode()
        att = self.Attachment.create({
            'name': 'roundtrip.bin',
            'raw': payload,
            'mimetype': 'application/octet-stream',
        })
        # routed to S3
        self.assertEqual(att._storage(), 'odusite_s3')
        key = att.store_fname
        self.assertTrue(key)
        # object physically present in the bucket with the exact bytes
        self.assertEqual(self._object_bytes(key), payload)
        # _file_read returns the same bytes (force a re-read from the backend)
        att.invalidate_recordset(['raw'])
        self.assertEqual(att._file_read(key), payload)
        self.assertEqual(att.raw, payload)
        # delete -> object gone from S3
        att.unlink()
        with self.assertRaises(self.ClientError):
            self.s3_client.get_object(Bucket=S3_BUCKET, Key=key)

    def test_dedup_same_checksum_single_object(self):
        payload = b'odusite-dedup-' + uuid.uuid4().hex.encode()
        a = self.Attachment.create({'name': 'a.bin', 'raw': payload,
                                     'mimetype': 'application/octet-stream'})
        b = self.Attachment.create({'name': 'b.bin', 'raw': payload,
                                    'mimetype': 'application/octet-stream'})
        self.assertEqual(a.store_fname, b.store_fname)
        # deleting one keeps the shared object (still referenced by the other)
        a.unlink()
        self.assertEqual(self._object_bytes(b.store_fname), payload)

    def test_presigned_url(self):
        att = self.Attachment.create({
            'name': 'private.pdf',
            'raw': b'%PDF-1.4 odusite ' + uuid.uuid4().hex.encode(),
            'mimetype': 'application/pdf',
        })
        url = att._odusite_presigned_url()
        self.assertTrue(url.startswith('http'))
        self.assertIn(S3_BUCKET, url)
        self.assertIn('X-Amz-Signature', url)

        # a non-S3 (web asset) attachment must raise
        asset = self.Attachment.create({
            'name': 'web.assets_backend.min.css',
            'res_model': 'ir.ui.view',
            'url': '/web/assets/1/deadbee/web.assets_backend.min.css',
            'mimetype': 'text/css',
            'type': 'binary',
            'public': True,
            'raw': b'body{color:red}',
        })
        self.assertNotEqual(asset._storage(), 'odusite_s3')
        with self.assertRaises(UserError):
            asset._odusite_presigned_url()

    def test_public_url_hybrid(self):
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('odusite.s3.public_base_url', 'https://media.example.com')

        partner = self.env['res.partner'].create({
            'name': 'S3 Hybrid Partner',
            'image_1920': PNG_1PX,
        })
        att = self.Attachment.sudo().search([
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', partner.id),
            ('res_field', '=', 'image_1920'),
        ], limit=1)
        self.assertTrue(att, "image_1920 attachment should exist")
        self.assertEqual(att._storage(), 'odusite_s3')
        att.public = True

        result = serializers.public_asset(partner, 'image_1920')
        self.assertTrue(result['proxy'].startswith('/web/image'),
                        "proxy should be a /web/image URL, got %r" % result['proxy'])
        self.assertEqual(result['original'],
                         'https://media.example.com/%s' % att.store_fname)
        self.assertTrue(result['original'].startswith('https://media.example.com/'))

    def test_public_url_none_without_public_base(self):
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('odusite.s3.public_base_url', '')
        partner = self.env['res.partner'].create({
            'name': 'S3 No Base Partner',
            'image_1920': PNG_1PX,
        })
        result = serializers.public_asset(partner, 'image_1920')
        self.assertIsNone(result['original'])
        self.assertTrue(result['proxy'].startswith('/web/image'))
