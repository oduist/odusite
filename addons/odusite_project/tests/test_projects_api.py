from odoo.tests.common import tagged

from odoo.addons.odusite_base.tests.common import OdusiteHttpCase


@tagged('post_install', '-at_install')
class TestProjectsApi(OdusiteHttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.portal_user = cls.create_portal_user(
            login='odusite.project@example.com', name='Odusite Project Tester')
        cls.partner = cls.portal_user.partner_id
        cls.other_user = cls.create_portal_user(
            login='odusite.project.other@example.com', name='Odusite Other Portal')

        # Portal visibility works like the stock project portal: the project
        # must be privacy_visibility='portal' and the partner a follower of
        # the project (project rule) and of each task (task rule).
        cls.project = cls.env['project.project'].create({
            'name': 'Odusite Portal Project',
            'privacy_visibility': 'portal',
        })
        cls.project.message_subscribe(partner_ids=cls.partner.ids)

        cls.task_open = cls.env['project.task'].create({
            'name': 'Odusite Open Task',
            'project_id': cls.project.id,
            'description': '<p>Fix the website header</p>',
        })
        cls.task_done = cls.env['project.task'].create({
            'name': 'Odusite Done Task',
            'project_id': cls.project.id,
        })
        cls.task_done.write({'state': '1_done'})
        (cls.task_open + cls.task_done).message_subscribe(partner_ids=cls.partner.ids)

    def _bearer(self, user=None):
        return self.make_access_token(user or self.portal_user)

    # -- /my/projects -------------------------------------------------------

    def test_projects_list(self):
        response, body = self.api('GET', '/my/projects?limit=100',
                                  bearer=self._bearer())
        self.assertEqual(response.status_code, 200, body)
        by_id = {project['id']: project for project in body['data']}
        self.assertIn(self.project.id, by_id)
        entry = by_id[self.project.id]
        self.assertEqual(entry['name'], 'Odusite Portal Project')
        self.assertEqual(entry['task_count'], 2)
        self.assertEqual(entry['open_task_count'], 1)

    def test_projects_list_requires_jwt(self):
        response, body = self.api('GET', '/my/projects')
        self.assert_api_error(response, body, 401, 'unauthorized')

    def test_project_detail_with_tasks(self):
        response, body = self.api('GET', f'/my/projects/{self.project.id}',
                                  bearer=self._bearer())
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertEqual(data['id'], self.project.id)
        task_ids = {task['id'] for task in data['tasks']}
        self.assertEqual(task_ids, {self.task_open.id, self.task_done.id})
        self.assertIn('total', body['meta'])

        # Task filters also apply to the embedded task list.
        response, body = self.api(
            'GET', f'/my/projects/{self.project.id}?state=open',
            bearer=self._bearer())
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual([task['id'] for task in body['data']['tasks']],
                         [self.task_open.id])

    def test_project_detail_access_token(self):
        token = self.project._portal_ensure_token()
        response, body = self.api(
            'GET', f'/my/projects/{self.project.id}?access_token={token}')
        self.assertEqual(response.status_code, 200, body)
        # Token-based access lists the project's tasks in sudo.
        task_ids = {task['id'] for task in body['data']['tasks']}
        self.assertEqual(task_ids, {self.task_open.id, self.task_done.id})

        response, body = self.api(
            'GET', f'/my/projects/{self.project.id}?access_token=wrong-token')
        self.assert_api_error(response, body, 403, 'forbidden')

    # -- /my/tasks ------------------------------------------------------------

    def test_tasks_list_and_filters(self):
        bearer = self._bearer()
        response, body = self.api('GET', '/my/tasks?limit=100', bearer=bearer)
        self.assertEqual(response.status_code, 200, body)
        ids = {task['id'] for task in body['data']}
        self.assertEqual(ids, {self.task_open.id, self.task_done.id})
        item = next(task for task in body['data'] if task['id'] == self.task_open.id)
        for key in ('id', 'name', 'project', 'stage', 'state', 'deadline',
                    'assignees', 'priority'):
            self.assertIn(key, item)
        self.assertEqual(item['project'],
                         {'id': self.project.id, 'name': self.project.name})
        self.assertEqual(item['state'], '01_in_progress')

        response, body = self.api(
            'GET', f'/my/tasks?project={self.project.id}&limit=100', bearer=bearer)
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual({task['id'] for task in body['data']},
                         {self.task_open.id, self.task_done.id})

        response, body = self.api('GET', '/my/tasks?state=open&limit=100',
                                  bearer=bearer)
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual([task['id'] for task in body['data']], [self.task_open.id])

        response, body = self.api('GET', '/my/tasks?state=closed&limit=100',
                                  bearer=bearer)
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual([task['id'] for task in body['data']], [self.task_done.id])

        response, body = self.api('GET', '/my/tasks?search=Open&limit=100',
                                  bearer=bearer)
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual([task['id'] for task in body['data']], [self.task_open.id])

        response, body = self.api('GET', '/my/tasks?state=bogus', bearer=bearer)
        self.assert_api_error(response, body, 400, 'bad_request')

        response, body = self.api('GET', '/my/tasks?project=abc', bearer=bearer)
        self.assert_api_error(response, body, 400, 'bad_request')

    # -- /my/tasks/<id> detail ---------------------------------------------------

    def test_task_detail(self):
        attachment = self.env['ir.attachment'].create({
            'name': 'spec.txt',
            'raw': b'Attached spec content',
            'res_model': 'project.task',
            'res_id': self.task_open.id,
            'mimetype': 'text/plain',
        })
        response, body = self.api('GET', f'/my/tasks/{self.task_open.id}',
                                  bearer=self._bearer())
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertEqual(data['id'], self.task_open.id)
        self.assertIn('Fix the website header', data['description_html'])
        self.assertEqual(data['subtasks'], [])

        attachments = {entry['id']: entry for entry in data['attachments']}
        self.assertIn(attachment.id, attachments)
        entry = attachments[attachment.id]
        self.assertEqual(entry['name'], 'spec.txt')
        self.assertEqual(entry['mimetype'], 'text/plain')
        # Attachment URLs are token-signed /web/content links.
        self.assertTrue(entry['url'].startswith(f'/web/content/{attachment.id}'))
        self.assertIn('access_token=', entry['url'])
        self.env.invalidate_all()
        self.assertIn(attachment.access_token, entry['url'])

    def test_task_detail_access_token(self):
        # project.task uses portal.mixin: record access via _portal_ensure_token.
        token = self.task_open._portal_ensure_token()
        response, body = self.api(
            'GET', f'/my/tasks/{self.task_open.id}?access_token={token}')
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(body['data']['id'], self.task_open.id)

        response, body = self.api(
            'GET', f'/my/tasks/{self.task_open.id}?access_token=wrong-token')
        self.assert_api_error(response, body, 403, 'forbidden')

    # -- Access control -------------------------------------------------------

    def test_other_portal_user_has_no_access(self):
        bearer = self._bearer(self.other_user)

        response, body = self.api('GET', '/my/projects?limit=100', bearer=bearer)
        self.assertEqual(response.status_code, 200, body)
        self.assertNotIn(self.project.id,
                         [project['id'] for project in body['data']])

        response, body = self.api('GET', '/my/tasks?limit=100', bearer=bearer)
        self.assertEqual(response.status_code, 200, body)
        self.assertNotIn(self.task_open.id, [task['id'] for task in body['data']])

        response, body = self.api('GET', f'/my/projects/{self.project.id}',
                                  bearer=bearer)
        self.assert_api_error(response, body, 403, 'forbidden')

        response, body = self.api('GET', f'/my/tasks/{self.task_open.id}',
                                  bearer=bearer)
        self.assert_api_error(response, body, 403, 'forbidden')

    def test_missing_records_404(self):
        response, body = self.api('GET', '/my/projects/99999999',
                                  bearer=self._bearer())
        self.assert_api_error(response, body, 404, 'not_found')
        response, body = self.api('GET', '/my/tasks/99999999',
                                  bearer=self._bearer())
        self.assert_api_error(response, body, 404, 'not_found')

    # -- Website form registration -----------------------------------------------

    def test_form_model_registration(self):
        forms = self.env['odusite.api']._form_models()
        self.assertIn('project.task', forms)
        self.assertIn('name', forms['project.task']['fields'])
        self.assertIn('name', forms['project.task']['required'])

    def test_generic_form_creates_task(self):
        # The generic form endpoint is provided by odusite_crm.
        crm_installed = self.env['ir.module.module'].sudo().search_count([
            ('name', '=', 'odusite_crm'), ('state', '=', 'installed'),
        ])
        if not crm_installed:
            self.skipTest('odusite_crm is not installed')

        response, body = self.api('POST', '/forms/generic/project.task', {
            'name': 'Website request',
            'description': 'Please call me back',
            'email_from': 'visitor@example.com',
        })
        self.assertEqual(response.status_code, 200, body)
        task = self.env['project.task'].browse(body['data']['id'])
        self.assertTrue(task.exists())
        self.assertEqual(task.name, 'Website request')
        self.assertEqual(task.email_from, 'visitor@example.com')

        # The required-field whitelist is enforced.
        response, body = self.api('POST', '/forms/generic/project.task',
                                  {'description': 'no name'})
        self.assert_api_error(response, body, 422, 'validation_error')
