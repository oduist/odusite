import secrets

from . import controllers
from . import lib
from . import models


def post_init_hook(env):
    icp = env['ir.config_parameter'].sudo()
    if not icp.get_param('odusite.token'):
        icp.set_param('odusite.token', secrets.token_hex(32))
    if not icp.get_param('odusite.jwt_secret'):
        icp.set_param('odusite.jwt_secret', secrets.token_hex(32))
