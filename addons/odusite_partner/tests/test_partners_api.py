from odoo.tests.common import tagged

from odoo.addons.odusite_base.tests.common import OdusiteHttpCase


@tagged('post_install', '-at_install')
class TestPartnersApi(OdusiteHttpCase):
    """Partner directory tests.

    grade/assigned/references/tags only exist when the optional
    website_crm_partner_assign / website_customer modules are installed; each
    branch is tested through runtime field-presence checks so the suite passes
    in both configurations.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env['res.partner']
        partner_fields = Partner._fields
        cls.has_assign = 'grade_id' in partner_fields
        cls.has_customer = 'website_tag_ids' in partner_fields
        cls.country_us = cls.env.ref('base.us')
        cls.country_de = cls.env.ref('base.de')
        cls.country_fr = cls.env.ref('base.fr')
        common = {'is_company': True, 'is_published': True}
        cls.alpha = Partner.create(dict(
            common,
            name='Odusite Alpha Systems',
            city='Austin',
            country_id=cls.country_us.id,
            website='https://alpha.example.com',
            website_short_description='Alpha short description',
            website_description='<p>Alpha builds rockets.</p>',
        ))
        cls.bravo = Partner.create(dict(
            common,
            name='Odusite Bravo GmbH',
            city='Berlin',
            country_id=cls.country_de.id,
            website_description='<p>Bravo brews beer.</p>',
        ))
        cls.charlie = Partner.create(dict(
            common,
            name='Odusite Charlie SARL',
            city='Paris',
            country_id=cls.country_fr.id,
            website_description='<p>Charlie makes cheese.</p>',
        ))
        cls.delta = Partner.create({
            'name': 'Odusite Delta Hidden',
            'is_company': True,
            'is_published': False,
            'city': 'Lyon',
            'country_id': cls.country_fr.id,
        })
        cls.grade = None
        if cls.has_assign:
            cls.grade = cls.env['res.partner.grade'].create({
                'name': 'Odusite Gold',
                'is_published': True,
            })
            cls.bravo.grade_id = cls.grade
            # charlie is a reference implemented by alpha.
            cls.charlie.assigned_partner_id = cls.alpha

    def _slug(self, record):
        return self.env['ir.http']._slug(record)

    def _ids(self, body):
        return {item['id'] for item in body['data']}

    # -- /partners list ------------------------------------------------------

    def test_partners_publish_gate(self):
        # Scoped by our unique search token: delta matches the search but is
        # unpublished, so it must never appear.
        response, body = self.api('GET', '/partners?search=Odusite')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._ids(body),
                         {self.alpha.id, self.bravo.id, self.charlie.id})
        item = next(i for i in body['data'] if i['id'] == self.alpha.id)
        for key in ('id', 'slug', 'name', 'logo', 'short_description',
                    'city', 'country', 'tags'):
            self.assertIn(key, item)
        self.assertEqual(item['city'], 'Austin')
        self.assertEqual(item['country'], self.country_us.name)
        self.assertEqual(item['short_description'], 'Alpha short description')

    def test_partners_default_list_smoke(self):
        response, body = self.api('GET', '/partners')
        self.assertEqual(response.status_code, 200)
        for key in ('total', 'page', 'limit', 'pages', 'facets'):
            self.assertIn(key, body['meta'])

    def test_partners_filter_country(self):
        # By ISO code.
        response, body = self.api('GET', '/partners?search=Odusite&country=US')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._ids(body), {self.alpha.id})
        # By id.
        response, body = self.api(
            'GET', f'/partners?search=Odusite&country={self.country_de.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._ids(body), {self.bravo.id})
        # Unknown ISO code.
        response, body = self.api('GET', '/partners?country=ZZ')
        self.assert_api_error(response, body, 400, 'bad_request')

    def test_partners_facets(self):
        response, body = self.api('GET', '/partners?search=Odusite')
        self.assertEqual(response.status_code, 200)
        facets = body['meta']['facets']
        self.assertIn('countries', facets)
        self.assertIn('grades', facets)
        us_facet = next(
            (c for c in facets['countries'] if c['id'] == self.country_us.id), None)
        self.assertTrue(us_facet, 'US facet missing')
        self.assertEqual(us_facet['code'], 'US')
        self.assertEqual(us_facet['count'], 1)
        if self.has_assign:
            grade_facet = next(
                (g for g in facets['grades'] if g['id'] == self.grade.id), None)
            self.assertTrue(grade_facet, 'grade facet missing')
            self.assertEqual(grade_facet['count'], 1)
        else:
            self.assertEqual(facets['grades'], [])

    def test_partners_kind_and_grade(self):
        if self.has_assign:
            # resellers = published companies with a published, active grade.
            response, body = self.api('GET', '/partners?search=Odusite&kind=resellers')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self._ids(body), {self.bravo.id})
            item = body['data'][0]
            self.assertEqual(item['grade'], {'id': self.grade.id, 'name': 'Odusite Gold'})
            # Explicit grade filter.
            response, body = self.api(
                'GET', f'/partners?search=Odusite&grade={self.grade.id}')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self._ids(body), {self.bravo.id})
            # customers = published partners with an assigning partner.
            response, body = self.api('GET', '/partners?search=Odusite&kind=customers')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self._ids(body), {self.charlie.id})
        else:
            # Fallback semantics: both kinds degrade to published companies,
            # and no grade key is serialized.
            for kind in ('resellers', 'customers'):
                response, body = self.api(
                    'GET', f'/partners?search=Odusite&kind={kind}')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self._ids(body),
                                 {self.alpha.id, self.bravo.id, self.charlie.id})
                self.assertNotIn('grade', body['data'][0])

    def test_partners_bad_kind(self):
        response, body = self.api('GET', '/partners?kind=suppliers')
        self.assert_api_error(response, body, 400, 'bad_request')
        self.assertEqual(body['error']['details']['allowed'],
                         ['customers', 'resellers'])

    # -- /partners/<ref> detail ------------------------------------------------

    def test_partner_detail(self):
        response, body = self.api('GET', f'/partners/{self._slug(self.alpha)}')
        self.assertEqual(response.status_code, 200)
        data = body['data']
        self.assertEqual(data['id'], self.alpha.id)
        self.assertIn('Alpha builds rockets', data['description_html'])
        self.assertEqual(data['website'], 'https://alpha.example.com')
        self.assertEqual(
            set(data['seo']), {'title', 'description', 'keywords', 'og_image'})
        if self.has_assign:
            self.assertEqual([r['id'] for r in data['references']], [self.charlie.id])
        else:
            self.assertNotIn('references', data)
        # Detail also resolves by plain id.
        response, body = self.api('GET', f'/partners/{self.bravo.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body['data']['id'], self.bravo.id)

    def test_partner_detail_not_found(self):
        response, body = self.api('GET', f'/partners/{self.delta.id}')
        self.assert_api_error(response, body, 404, 'not_found')

        response, body = self.api('GET', '/partners/99999999')
        self.assert_api_error(response, body, 404, 'not_found')

        response, body = self.api('GET', '/partners/not-a-slug')
        self.assert_api_error(response, body, 404, 'not_found')
