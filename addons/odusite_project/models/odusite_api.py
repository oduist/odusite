from odoo import models


class OdusiteApi(models.AbstractModel):
    _inherit = 'odusite.api'

    def _portal_counters(self, counters):
        # Mirrors project portal _prepare_home_portal_values
        # (project/controllers/portal.py).
        values = super()._portal_counters(counters)
        if 'projects' in counters:
            project_model = self.env['project.project']
            values['projects'] = (
                project_model.search_count([]) if project_model.has_access('read') else 0
            )
        if 'tasks' in counters:
            task_model = self.env['project.task']
            values['tasks'] = (
                task_model.search_count([('project_id', '!=', False)])
                if task_model.has_access('read') else 0
            )
        return values

    def _chatter_models(self):
        return super()._chatter_models() | {'project.task', 'project.project'}

    def _form_models(self):
        # Website suggestion form for tasks, like website_project
        # (website_project/controllers/main.py `extract_data`: name,
        # description, email_from on project.task).
        forms = super()._form_models()
        forms['project.task'] = {
            'fields': ['name', 'description', 'email_from'],
            'required': ['name'],
        }
        return forms
