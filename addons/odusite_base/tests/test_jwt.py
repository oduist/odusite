import time

from odoo.tests.common import BaseCase, tagged

from ..lib import jwt as jwt_lib


@tagged('post_install', '-at_install')
class TestJwtLib(BaseCase):

    SECRET = 'unit-test-secret'

    def test_sign_verify_roundtrip(self):
        payload = {'sub': 42, 'typ': 'access', 'exp': time.time() + 60}
        token = jwt_lib.sign(payload, self.SECRET)
        self.assertEqual(len(token.split('.')), 3)
        decoded = jwt_lib.verify(token, self.SECRET)
        self.assertEqual(decoded['sub'], 42)
        self.assertEqual(decoded['typ'], 'access')

    def test_expired_token(self):
        token = jwt_lib.sign({'sub': 1, 'exp': time.time() - 1}, self.SECRET)
        with self.assertRaises(jwt_lib.ExpiredToken):
            jwt_lib.verify(token, self.SECRET)

    def test_wrong_secret(self):
        token = jwt_lib.sign({'sub': 1}, self.SECRET)
        with self.assertRaises(jwt_lib.InvalidToken):
            jwt_lib.verify(token, 'other-secret')

    def test_tampered_payload(self):
        token = jwt_lib.sign({'sub': 1, 'exp': time.time() + 60}, self.SECRET)
        header, payload, signature = token.split('.')
        forged_payload = jwt_lib._b64encode(b'{"sub": 999}')
        with self.assertRaises(jwt_lib.InvalidToken):
            jwt_lib.verify(f'{header}.{forged_payload}.{signature}', self.SECRET)

    def test_malformed_tokens(self):
        for bad in ('', 'a.b', 'a.b.c.d', 'not base64 at all', '..'):
            with self.assertRaises(jwt_lib.InvalidToken):
                jwt_lib.verify(bad, self.SECRET)

    def test_no_exp_is_valid(self):
        token = jwt_lib.sign({'sub': 7}, self.SECRET)
        self.assertEqual(jwt_lib.verify(token, self.SECRET)['sub'], 7)
