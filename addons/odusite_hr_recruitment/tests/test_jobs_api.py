from odoo.tests.common import tagged

from odoo.addons.odusite_base.tests.common import OdusiteHttpCase

CV_FILE = ('cv.pdf', b'%PDF-1.4 fake', 'application/pdf')
APPLY_PAYLOAD = {
    'name': 'John Tester',
    'email': 'john.tester@example.com',
    'phone': '+1 555 0199',
}


@tagged('post_install', '-at_install')
class TestJobsApi(OdusiteHttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.country_be = cls.env.ref('base.be')
        cls.department = cls.env['hr.department'].create({'name': 'Odusite R&D'})
        cls.contract_type = cls.env['hr.contract.type'].create(
            {'name': 'Odusite Full-Time'})
        cls.office = cls.env['res.partner'].create({
            'name': 'Odusite Brussels Office',
            'is_company': True,
            'city': 'Brussels',
            'country_id': cls.country_be.id,
        })
        cls.job_office = cls.env['hr.job'].create({
            'name': 'Odusite Backend Developer',
            'department_id': cls.department.id,
            'contract_type_id': cls.contract_type.id,
            'address_id': cls.office.id,
            'is_published': True,
            'website_description': '<p>Backend wizardry required.</p>',
        })
        # No work location = remote (upstream semantics).
        cls.job_remote = cls.env['hr.job'].create({
            'name': 'Odusite Remote Designer',
            'address_id': False,
            'is_published': True,
            'website_description': '<p>Design from anywhere.</p>',
        })
        cls.job_unpublished = cls.env['hr.job'].create({
            'name': 'Odusite Secret Role',
            'department_id': cls.department.id,
            'address_id': cls.office.id,
            'is_published': False,
        })

    def _slug(self, record):
        return self.env['ir.http']._slug(record)

    def _ids(self, body):
        return {item['id'] for item in body['data']}

    def _apply(self, job, payload=None, files='default'):
        if files == 'default':
            files = {'cv': CV_FILE}
        return self.api('POST', f'/jobs/{job.id}/apply',
                        payload=dict(APPLY_PAYLOAD, **(payload or {})),
                        files=files)

    # -- /jobs list ------------------------------------------------------------

    def test_jobs_publish_gate(self):
        response, body = self.api('GET', '/jobs?limit=100')
        self.assertEqual(response.status_code, 200)
        ids = self._ids(body)
        self.assertIn(self.job_office.id, ids)
        self.assertIn(self.job_remote.id, ids)
        self.assertNotIn(self.job_unpublished.id, ids)
        item = next(i for i in body['data'] if i['id'] == self.job_office.id)
        self.assertEqual(item['slug'], self._slug(self.job_office))
        self.assertEqual(item['department'],
                         {'id': self.department.id, 'name': 'Odusite R&D'})
        self.assertEqual(item['location'],
                         {'city': 'Brussels', 'country': self.country_be.name})
        self.assertEqual(item['employment_type'],
                         {'id': self.contract_type.id, 'name': 'Odusite Full-Time'})
        self.assertFalse(item['is_remote'])
        self.assertTrue(item['published_date'])

    def test_jobs_filter_department(self):
        response, body = self.api('GET', f'/jobs?department={self.department.id}')
        self.assertEqual(response.status_code, 200)
        # The unpublished job shares the department but stays hidden.
        self.assertEqual(self._ids(body), {self.job_office.id})

    def test_jobs_filter_remote(self):
        response, body = self.api('GET', '/jobs?remote=1&limit=100')
        self.assertEqual(response.status_code, 200)
        ids = self._ids(body)
        self.assertIn(self.job_remote.id, ids)
        self.assertNotIn(self.job_office.id, ids)
        self.assertTrue(all(item['is_remote'] for item in body['data']))

    def test_jobs_filter_country(self):
        for ref in ('BE', self.country_be.id):
            response, body = self.api('GET', f'/jobs?country={ref}&limit=100')
            self.assertEqual(response.status_code, 200)
            ids = self._ids(body)
            self.assertIn(self.job_office.id, ids)
            self.assertNotIn(self.job_remote.id, ids)
            self.assertTrue(all(item['location']['country'] == self.country_be.name
                                for item in body['data']))
        response, body = self.api('GET', '/jobs?country=ZZ')
        self.assert_api_error(response, body, 400, 'bad_request')

    def test_jobs_facets(self):
        response, body = self.api('GET', '/jobs')
        self.assertEqual(response.status_code, 200)
        facets = body['meta']['facets']
        for key in ('departments', 'employment_types', 'countries'):
            self.assertIn(key, facets)
        self.assertIn({'id': self.department.id, 'name': 'Odusite R&D', 'count': 1},
                      facets['departments'])
        self.assertIn({'id': self.contract_type.id, 'name': 'Odusite Full-Time',
                       'count': 1}, facets['employment_types'])
        be_facet = next(
            (c for c in facets['countries'] if c['id'] == self.country_be.id), None)
        self.assertTrue(be_facet, 'BE country facet missing')
        self.assertGreaterEqual(be_facet['count'], 1)

    # -- /jobs/<ref> detail -----------------------------------------------------

    def test_job_detail(self):
        response, body = self.api('GET', f'/jobs/{self.job_office.id}')
        self.assertEqual(response.status_code, 200)
        data = body['data']
        self.assertEqual(data['id'], self.job_office.id)
        self.assertIn('Backend wizardry required', data['description_html'])
        self.assertEqual(
            set(data['seo']), {'title', 'description', 'keywords', 'og_image'})
        # Also resolvable by slug.
        response, body = self.api('GET', f'/jobs/{self._slug(self.job_remote)}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body['data']['id'], self.job_remote.id)
        self.assertTrue(body['data']['is_remote'])

    def test_job_detail_not_found(self):
        response, body = self.api('GET', f'/jobs/{self.job_unpublished.id}')
        self.assert_api_error(response, body, 404, 'not_found')

        response, body = self.api('GET', '/jobs/99999999')
        self.assert_api_error(response, body, 404, 'not_found')

    # -- POST /jobs/<id>/apply ---------------------------------------------------

    def test_apply_valid(self):
        response, body = self._apply(
            self.job_office, payload={'short_introduction': 'I love testing'})
        self.assertEqual(response.status_code, 200, body)
        applicant = self.env['hr.applicant'].browse(body['data']['id'])
        self.assertTrue(applicant.exists())
        self.assertEqual(applicant.partner_name, 'John Tester')
        self.assertEqual(applicant.email_from, 'john.tester@example.com')
        self.assertEqual(applicant.partner_phone, '+1 555 0199')
        self.assertEqual(applicant.job_id, self.job_office)
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'hr.applicant'),
            ('res_id', '=', applicant.id),
        ])
        self.assertEqual(len(attachment), 1)
        self.assertEqual(attachment.name, 'cv.pdf')
        self.assertEqual(attachment.raw, b'%PDF-1.4 fake')

    def test_apply_missing_cv(self):
        response, body = self._apply(self.job_office, files=None)
        self.assert_api_error(response, body, 422, 'validation_error')
        self.assertEqual(body['error']['details']['fields'], {'cv': 'required'})

    def test_apply_missing_everything(self):
        response, body = self.api('POST', f'/jobs/{self.job_office.id}/apply',
                                  payload={})
        self.assert_api_error(response, body, 422, 'validation_error')
        self.assertEqual(set(body['error']['details']['fields']),
                         {'name', 'email', 'phone', 'cv'})

    def test_apply_invalid_email(self):
        response, body = self._apply(self.job_office,
                                     payload={'email': 'not-an-email'})
        self.assert_api_error(response, body, 422, 'validation_error')
        self.assertEqual(body['error']['details']['fields'], {'email': 'invalid'})

    def test_apply_duplicate(self):
        response, body = self._apply(self.job_office)
        self.assertEqual(response.status_code, 200, body)
        applicant = self.env['hr.applicant'].browse(body['data']['id'])
        self.assertEqual(applicant.application_status, 'ongoing')
        # Same email, same job, first application still ongoing.
        response, body = self._apply(self.job_office)
        self.assert_api_error(response, body, 409, 'already_applied')
        # A different job is still open to the same candidate.
        response, body = self._apply(self.job_remote)
        self.assertEqual(response.status_code, 200, body)

    def test_apply_unpublished_job(self):
        response, body = self._apply(self.job_unpublished)
        self.assert_api_error(response, body, 404, 'not_found')
