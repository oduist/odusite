from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestOffloadPolicy(TransactionCase):
    """Pure policy tests: no S3 connectivity required (uses in-memory .new())."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Attachment = cls.env['ir.attachment']

    def _new(self, **vals):
        base = {'name': 'x', 'type': 'binary'}
        base.update(vals)
        return self.Attachment.new(base)

    def test_web_asset_view_not_offloadable(self):
        att = self._new(
            name='web.assets_backend.min.css',
            res_model='ir.ui.view',
            url='/web/assets/1/abc123/web.assets_backend.min.css',
            mimetype='text/css',
        )
        self.assertFalse(att._odusite_s3_offloadable())

    def test_asset_mimetypes_not_offloadable(self):
        self.assertFalse(self._new(mimetype='text/css')._odusite_s3_offloadable())
        self.assertFalse(self._new(mimetype='application/javascript')._odusite_s3_offloadable())
        self.assertFalse(self._new(mimetype='text/scss')._odusite_s3_offloadable())

    def test_web_assets_url_or_name_not_offloadable(self):
        self.assertFalse(self._new(url='/web/assets/x')._odusite_s3_offloadable())
        self.assertFalse(self._new(name='/web/assets/x')._odusite_s3_offloadable())

    def test_content_is_offloadable(self):
        self.assertTrue(self._new(
            name='hero.png', mimetype='image/png',
            res_model='product.template')._odusite_s3_offloadable())
        self.assertTrue(self._new(
            name='invoice.pdf', mimetype='application/pdf')._odusite_s3_offloadable())

    def test_empty_recordset_defaults_offloadable(self):
        # model-level (batched write) default must offload content by default
        self.assertTrue(self.Attachment._odusite_s3_offloadable())

    def test_vals_policy(self):
        self.assertFalse(self.Attachment._odusite_s3_offloadable_vals({'res_model': 'ir.ui.view'}))
        self.assertFalse(self.Attachment._odusite_s3_offloadable_vals({'mimetype': 'application/javascript'}))
        self.assertFalse(self.Attachment._odusite_s3_offloadable_vals(
            {'url': '/web/assets/1/x/web.assets_backend.min.js'}))
        self.assertTrue(self.Attachment._odusite_s3_offloadable_vals(
            {'name': 'photo.png', 'mimetype': 'image/png'}))
