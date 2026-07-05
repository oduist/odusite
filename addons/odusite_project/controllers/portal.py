"""Portal projects & tasks endpoints (see specs/modules/odusite_project.md).

Domains, search inputs and access patterns mirror the stock project portal
controller (project/controllers/portal.py) and, for timesheets, the
hr_timesheet portal controller.
"""

from odoo.fields import Domain
from odoo.http import request

from odoo.addons.odusite_base.controllers.api import (
    API_PREFIX,
    ApiError,
    list_meta,
    odusite_route,
    parse_pagination,
)
from odoo.addons.odusite_base.lib import serializers
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.project.models.project_task import CLOSED_STATES

# Public order keys -> ORM order (subset of project/controllers/portal.py
# `_prepare_searchbar_sortings` / `_task_get_searchbar_sortings`).
PROJECT_ORDER_WHITELIST = {
    'date': 'create_date desc',
    'name': 'name',
}
TASK_ORDER_WHITELIST = {
    'date': 'id desc',
    'name': 'name',
    'project': 'project_id, stage_id',
    'stage': 'stage_id, project_id',
    'state': 'state',
    'priority': 'priority desc',
    'deadline': 'date_deadline asc',
}


class OdusiteProjectPortal(CustomerPortal):

    # === Helpers === #

    def _serialize_project(self, project):
        return {
            'id': project.id,
            'name': project.name,
            'task_count': project.task_count,
            'open_task_count': project.open_task_count,
        }

    def _serialize_task(self, task):
        project = task.project_id
        return {
            'id': task.id,
            'name': task.name,
            'project': {'id': project.id, 'name': project.sudo().name} if project else None,
            'stage': task.stage_id.name or '',
            'state': task.state,
            'deadline': serializers.datetime_utc(task.date_deadline),
            # The portal template shows assignees through sudo
            # (project_portal_project_task_templates.xml).
            'assignees': task.sudo().user_ids.mapped('name'),
            'priority': task.priority,
        }

    def _task_list(self, params, base_domain, su=False):
        """Search portal-visible tasks, stock pattern
        (project/controllers/portal.py `_prepare_tasks_values`): restrict the
        domain with the user's record rules, then search in sudo. ``su`` is
        only True for token-based access to a single project's tasks."""
        page, limit, offset, order = parse_pagination(
            params, order_whitelist=TASK_ORDER_WHITELIST, default_order='date',
        )
        task_model = request.env['project.task']
        domain = Domain.AND([base_domain, [('has_template_ancestor', '=', False)]])
        if not su:
            if not task_model.has_access('read'):
                return [], list_meta(0, page, limit)
            domain &= Domain(request.env['ir.rule']._compute_domain('project.task', 'read'))

        state = params.get('state')
        if state:
            if state == 'open':
                domain &= Domain('state', 'not in', list(CLOSED_STATES))
            elif state == 'closed':
                domain &= Domain('state', 'in', list(CLOSED_STATES))
            else:
                raise ApiError(400, 'bad_request', f'Unsupported state filter: {state}',
                               {'allowed': ['open', 'closed']})

        search = params.get('search')
        if search:
            # Same default search input as the stock portal
            # (`_task_get_search_domain`).
            domain &= Domain.OR([[('name', 'ilike', search)], [('id', 'ilike', search)]])

        task_sudo_model = task_model.sudo()
        total = task_sudo_model.search_count(domain)
        tasks = task_sudo_model.search(domain, order=order, limit=limit, offset=offset)
        return [self._serialize_task(task) for task in tasks], list_meta(total, page, limit)

    def _task_timesheet_summary(self, task_sudo):
        """Timesheet summary, only when hr_timesheet is installed
        (guarded: account.analytic.line model + timesheet fields present).
        Uses the portal timesheet domain like the stock task report
        (hr_timesheet/controllers/portal.py `_show_task_report`)."""
        if 'account.analytic.line' not in request.env \
                or 'timesheet_ids' not in task_sudo._fields:
            return None
        if 'allow_timesheets' in task_sudo._fields and not task_sudo.allow_timesheets:
            return None
        portal_domain = request.env['account.analytic.line']._timesheet_get_portal_domain()
        domain = Domain.AND([portal_domain, [('task_id', '=', task_sudo.id)]])
        lines = request.env['account.analytic.line'].sudo().search(domain, order='date desc')
        return {
            'total_hours': sum(lines.mapped('unit_amount')),
            'lines': [
                {
                    'date': serializers.date_iso(line.date),
                    'name': line.name or '',
                    'hours': line.unit_amount,
                }
                for line in lines
            ],
        }

    def _task_attachments(self, task_sudo):
        """Attachments with generated access tokens, served through
        /web/content like the stock task portal page
        (project/controllers/portal.py `portal_my_task` +
        project_portal_project_task_templates.xml)."""
        attachments_sudo = task_sudo.attachment_ids
        attachments_sudo.generate_access_token()
        return [
            {
                'id': attachment.id,
                'name': attachment.name,
                'url': f'/web/content/{attachment.id}?access_token={attachment.access_token}',
                'mimetype': attachment.mimetype,
            }
            for attachment in attachments_sudo
        ]

    # === Endpoints === #

    @odusite_route(f'{API_PREFIX}/my/projects', methods=['GET'], auth_user=True)
    def odusite_my_projects(self, **kwargs):
        page, limit, offset, order = parse_pagination(
            kwargs, order_whitelist=PROJECT_ORDER_WHITELIST, default_order='date',
        )
        # Stock portal domain (`_prepare_project_domain`); portal record
        # rules apply through the JWT user's environment.
        domain = [('is_template', '=', False)]
        project_model = request.env['project.project']
        total = project_model.search_count(domain)
        projects = project_model.search(domain, order=order, limit=limit, offset=offset)
        return (
            [self._serialize_project(project) for project in projects],
            list_meta(total, page, limit),
        )

    @odusite_route(f'{API_PREFIX}/my/projects/<int:project_id>', methods=['GET'])
    def odusite_my_project_detail(self, project_id, access_token=None, **kwargs):
        project_sudo = self._document_check_access('project.project', project_id, access_token)
        # Token-based public access searches the project's tasks in sudo,
        # like the stock project page (portal.py `_project_get_page_view_values`).
        su = bool(access_token) and request.env.user._is_public()
        tasks, meta = self._task_list(kwargs, [('project_id', '=', project_sudo.id)], su=su)
        data = self._serialize_project(project_sudo)
        data['tasks'] = tasks
        return data, meta

    @odusite_route(f'{API_PREFIX}/my/tasks', methods=['GET'], auth_user=True)
    def odusite_my_tasks(self, **kwargs):
        base_domain = [('project_id', '!=', False)]
        project_id = kwargs.get('project')
        if project_id:
            if not str(project_id).isdigit():
                raise ApiError(400, 'bad_request', 'Invalid project filter.')
            base_domain.append(('project_id', '=', int(project_id)))
        return self._task_list(kwargs, base_domain)

    @odusite_route(f'{API_PREFIX}/my/tasks/<int:task_id>', methods=['GET'])
    def odusite_my_task_detail(self, task_id, access_token=None, **kwargs):
        task_sudo = self._document_check_access('project.task', task_id, access_token)
        data = self._serialize_task(task_sudo)
        data.update({
            'description_html': serializers.html_field(task_sudo, 'description'),
            'attachments': self._task_attachments(task_sudo),
            'subtasks': [
                {'id': subtask.id, 'name': subtask.name, 'state': subtask.state}
                for subtask in task_sudo.child_ids
                if not subtask.has_template_ancestor
            ],
        })
        timesheets = self._task_timesheet_summary(task_sudo)
        if timesheets is not None:
            data['timesheets'] = timesheets
        return data
