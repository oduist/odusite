from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    odusite_allow_signup = fields.Boolean(
        string='Allow public sign up',
        help="Let visitors create their own portal account from the Astro site "
             "(with email double opt-in). Technically this flips the standard "
             "auth_signup.invitation_scope system parameter between 'b2c' (free "
             "sign up — enabled) and 'b2b' (on invitation only — disabled), "
             "which res.users._get_signup_invitation_scope() reads to gate "
             "POST /odusite/v1/auth/signup.",
    )

    def get_values(self):
        res = super().get_values()
        # Read the parameter row directly (ORM search sees writes made earlier
        # in the same transaction), bypassing get_param's ormcache — which is
        # not invalidated per-default-key within a single transaction and would
        # otherwise return a stale value right after set_values.
        param = self.env['ir.config_parameter'].sudo().search(
            [('key', '=', 'auth_signup.invitation_scope')], limit=1)
        res['odusite_allow_signup'] = param.value == 'b2c'
        return res

    def set_values(self):
        super().set_values()
        # Written after super() so the boolean always wins over the stock
        # auth_signup_uninvited selection that maps to the same parameter.
        self.env['ir.config_parameter'].sudo().set_param(
            'auth_signup.invitation_scope',
            'b2c' if self.odusite_allow_signup else 'b2b',
        )
