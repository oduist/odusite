from odoo import api, models


class ForumPostVote(models.Model):
    _inherit = 'forum.post.vote'

    # Vote counts are stored computes and never go through forum.post.write(),
    # so relay vote changes to the post's webhook queue here. The queue dedups
    # pending events per record, which throttles vote bursts (see spec).

    @api.model_create_multi
    def create(self, vals_list):
        votes = super().create(vals_list)
        votes.post_id._odusite_enqueue('updated')
        return votes

    def write(self, vals):
        res = super().write(vals)
        if 'vote' in vals:
            self.post_id._odusite_enqueue('updated')
        return res
