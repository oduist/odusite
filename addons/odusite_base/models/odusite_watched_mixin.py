from odoo import api, models


class OdusiteWatchedMixin(models.AbstractModel):
    """Mixin enqueueing cache-invalidation webhook events on relevant changes.

    Usage in an odusite module::

        class BlogPost(models.Model):
            _name = 'blog.post'
            _inherit = ['blog.post', 'odusite.watched.mixin']
            _odusite_tag = 'blog'
            _odusite_watch_fields = ('name', 'content', 'tag_ids', 'post_date')

    ``is_published`` (when the model has it) is always watched; publish
    transitions produce dedicated published/unpublished events and unpublished
    records don't emit update events.
    """
    _name = 'odusite.watched.mixin'
    _description = 'Odusite watched model mixin'

    _odusite_tag = None
    _odusite_watch_fields = ()

    def _odusite_tags(self):
        self.ensure_one()
        tag = self._odusite_tag or self._name.replace('.', '-')
        return [tag, f'{tag}:{self.id}']

    def _odusite_has_publish_field(self):
        return 'is_published' in self._fields

    def _odusite_is_published(self):
        self.ensure_one()
        return self.is_published if self._odusite_has_publish_field() else True

    def _odusite_change_is_relevant(self, vals):
        if not self._odusite_watch_fields:
            return True
        watched = set(self._odusite_watch_fields)
        if self._odusite_has_publish_field():
            watched.add('is_published')
            watched.add('website_published')
        return bool(watched & set(vals))

    def _odusite_enqueue(self, event):
        queue = self.env['odusite.webhook.event'].sudo()
        for record in self:
            queue._enqueue(record._name, record.id, event, record._odusite_tags())

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.filtered(lambda r: r._odusite_is_published())._odusite_enqueue('created')
        return records

    def write(self, vals):
        has_publish = self._odusite_has_publish_field()
        published_before = {r.id: r.is_published for r in self} if has_publish else {}
        res = super().write(vals)
        for record in self:
            if has_publish:
                was = published_before.get(record.id)
                now = record.is_published
                if not was and now:
                    record._odusite_enqueue('published')
                    continue
                if was and not now:
                    record._odusite_enqueue('unpublished')
                    continue
                if not now:
                    continue
            if record._odusite_change_is_relevant(vals):
                record._odusite_enqueue('updated')
        return res

    def unlink(self):
        self.filtered(lambda r: r._odusite_is_published())._odusite_enqueue('deleted')
        return super().unlink()
