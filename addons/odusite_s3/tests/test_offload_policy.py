from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestOffloadPolicy(TransactionCase):
    """Routing policy (``_odusite_s3_should_offload``): decided from mimetype +
    size and gated on an active config. No S3 network needed — only the config
    params so the policy is 'active' (boto3 is installed in the test image)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Attachment = cls.env['ir.attachment']
        icp = cls.env['ir.config_parameter'].sudo()
        icp.set_param('odusite.s3.enabled', 'True')
        icp.set_param('odusite.s3.bucket', 'odusite-media')
        icp.set_param('odusite.s3.access_key', 'test')
        icp.set_param('odusite.s3.secret_key', 'test')

    def should(self, mimetype, size):
        return self.Attachment._odusite_s3_should_offload(mimetype, size)

    def test_web_assets_stay_local(self):
        for mt in ('text/css', 'application/javascript', 'text/javascript', 'text/scss'):
            self.assertFalse(self.should(mt, 20_000), mt)

    def test_small_images_stay_local(self):
        # default keep_images_below_kb = 50
        self.assertFalse(self.should('image/png', 10_000))
        self.assertTrue(self.should('image/png', 200_000))

    def test_keep_local_mimetypes(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'odusite.s3.keep_local_mimetypes', 'application/xml, text/')
        self.assertFalse(self.should('application/xml', 100_000))
        self.assertFalse(self.should('text/plain', 100_000))
        self.assertTrue(self.should('application/pdf', 100_000))

    def test_regular_content_offloads(self):
        self.assertTrue(self.should('application/pdf', 100_000))
        self.assertTrue(self.should('image/png', 500_000))
        self.assertTrue(self.should(None, 100))  # unknown mimetype -> offload

    def test_disabled_never_offloads(self):
        self.env['ir.config_parameter'].sudo().set_param('odusite.s3.enabled', 'False')
        self.assertFalse(self.should('application/pdf', 100_000))
