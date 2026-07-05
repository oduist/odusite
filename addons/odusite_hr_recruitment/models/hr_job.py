from odoo import models


class HrJob(models.Model):
    _name = 'hr.job'
    _inherit = ['hr.job', 'odusite.watched.mixin']
    _odusite_tag = 'jobs'
    _odusite_watch_fields = (
        'name', 'website_description', 'job_details',
        'department_id', 'address_id', 'contract_type_id',
    )
