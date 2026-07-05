from odoo import models


class OdusiteApi(models.AbstractModel):
    """Extension registry for odusite modules.

    Other odusite addons ``_inherit = 'odusite.api'`` and extend these hooks
    (always call ``super()`` and merge results).
    """
    _name = 'odusite.api'
    _description = 'Odusite API hook registry'

    def _sitemap_entries(self, website):
        """Return a list of {'url': str, 'lastmod': datetime|None} for every
        published entity the site must include in sitemap.xml."""
        return []

    def _portal_counters(self, counters):
        """Return {counter_key: int} for the requested ``counters`` keys.
        Mirrors portal ``_prepare_home_portal_values``: compute a counter only
        when its key is in ``counters``."""
        return {}

    def _chatter_models(self):
        """Whitelist of models reachable through the generic chatter API."""
        return set()

    def _form_models(self):
        """Whitelist for the generic form endpoint:
        {model_name: {'fields': [...], 'required': [...]}}."""
        return {}
