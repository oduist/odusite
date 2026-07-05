from odoo import http
from odoo.fields import Domain
from odoo.http import request
from odoo.tools import email_normalize, escape_psql
from odoo.tools.mail import plaintext2html

from odoo.addons.odusite_base.controllers.api import (
    API_PREFIX,
    ApiError,
    list_meta,
    odusite_route,
    parse_pagination,
)
from odoo.addons.odusite_base.lib import serializers

JOB_ORDER = 'sequence, no_of_recruitment desc, id'


class OdusiteHrRecruitmentController(http.Controller):

    def _published_job_domain(self):
        return Domain.AND([
            request.website.website_domain(),
            [('is_published', '=', True)],
        ])

    def _ref_id(self, value, label):
        _, record_id = serializers.unslug(str(value))
        if not record_id:
            raise ApiError(400, 'bad_request', f'Invalid {label}: {value}')
        return record_id

    def _country_id(self, value):
        value = str(value)
        if not value.isdigit() and len(value) == 2 and value.isalpha():
            country = request.env['res.country'].sudo().search(
                [('code', '=', value.upper())], limit=1)
            if not country:
                raise ApiError(400, 'bad_request', f'Unknown country code: {value}')
            return country.id
        return self._ref_id(value, 'country')

    def _job_domain(self, department=None, country=None, employment_type=None,
                    remote=None, search=None, **kwargs):
        domain = self._published_job_domain()
        if department:
            domain &= Domain('department_id', '=', self._ref_id(department, 'department'))
        if employment_type:
            domain &= Domain('contract_type_id', '=', self._ref_id(employment_type, 'employment_type'))
        if country:
            domain &= Domain('address_id.country_id', '=', self._country_id(country))
        if remote and str(remote).lower() in ('1', 'true', 'yes'):
            # Upstream treats jobs without a work location as remote.
            domain &= Domain('address_id', '=', False)
        if search:
            domain &= Domain.OR([
                [('name', 'ilike', search)],
                [('website_description', 'ilike', search)],
            ])
        return domain

    def _job_facets(self, **kwargs):
        """Departments/countries/types with counts. Like the upstream /jobs
        page, each facet is computed with every filter applied except its
        own (remote is disabled together with country)."""
        Job = request.env['hr.job'].sudo()
        department_groups = Job._read_group(
            self._job_domain(**dict(kwargs, department=None)),
            ['department_id'], ['__count'])
        type_groups = Job._read_group(
            self._job_domain(**dict(kwargs, employment_type=None)),
            ['contract_type_id'], ['__count'])
        country_counts = {}
        address_groups = Job._read_group(
            self._job_domain(**dict(kwargs, country=None, remote=None)),
            ['address_id'], ['__count'])
        for address, count in address_groups:
            country = address.country_id if address else request.env['res.country']
            entry = country_counts.setdefault(country.id or None, {
                'id': country.id or None,
                'code': country.code or None,
                'name': country.name or None,
                'count': 0,
            })
            entry['count'] += count
        return {
            'departments': [
                {'id': department.id, 'name': department.name, 'count': count}
                for department, count in department_groups if department
            ],
            'employment_types': [
                {'id': contract_type.id, 'name': contract_type.name, 'count': count}
                for contract_type, count in type_groups if contract_type
            ],
            # id/code/name = None counts jobs without a location (remote).
            'countries': list(country_counts.values()),
        }

    def _serialize_job(self, job):
        address = job.address_id
        department = job.department_id
        contract_type = job.contract_type_id
        return {
            'id': job.id,
            'slug': serializers.slug(job),
            'name': job.name,
            'department': ({'id': department.id, 'name': department.name}
                           if department else None),
            'location': {
                'city': (address.city or '') if address else '',
                'country': (address.country_id.name or '') if address else '',
            },
            'employment_type': ({'id': contract_type.id, 'name': contract_type.name}
                                if contract_type else None),
            'is_remote': not address,
            'published_date': serializers.date_iso(job.published_date),
        }

    def _get_published_job(self, ref):
        _, job_id = serializers.unslug(str(ref))
        if not job_id:
            raise ApiError(404, 'not_found', 'Job not found.')
        job = request.env['hr.job'].sudo().browse(job_id).exists()
        if not job or not job.filtered_domain(self._published_job_domain()):
            raise ApiError(404, 'not_found', 'Job not found.')
        return job

    def _has_recent_application(self, job, email, phone, linkedin):
        """Blocking part of the upstream check_recent_application logic: an
        ongoing application on the same job for the same candidate
        (matched on email/phone/linkedin)."""
        candidate_domains = [Domain('email_normalized', '=', email_normalize(email))]
        if phone:
            candidate_domains.append(Domain('partner_phone', '=', phone))
        if linkedin:
            candidate_domains.append(Domain('linkedin_profile', '=ilike', escape_psql(linkedin)))
        return bool(request.env['hr.applicant'].sudo().search_count(Domain.AND([
            Domain.OR(candidate_domains),
            [
                ('job_id', '=', job.id),
                ('job_id.website_id', 'in', [request.website.id, False]),
                ('application_status', '=', 'ongoing'),
            ],
        ]), limit=1))

    @odusite_route(f'{API_PREFIX}/jobs', methods=['GET'])
    def jobs(self, **kwargs):
        page, limit, offset, _order = parse_pagination(kwargs)
        domain = self._job_domain(**kwargs)
        Job = request.env['hr.job'].sudo()
        total = Job.search_count(domain)
        jobs = Job.search(domain, limit=limit, offset=offset, order=JOB_ORDER)
        meta = list_meta(total, page, limit, facets=self._job_facets(**kwargs))
        return [self._serialize_job(job) for job in jobs], meta

    @odusite_route(f'{API_PREFIX}/jobs/<string:job_ref>', methods=['GET'])
    def job_detail(self, job_ref, **kwargs):
        job = self._get_published_job(job_ref)
        data = self._serialize_job(job)
        data.update({
            'description_html': (serializers.html_field(job, 'website_description')
                                 + serializers.html_field(job, 'job_details')),
            'seo': serializers.seo(job),
        })
        return data

    @odusite_route(f'{API_PREFIX}/jobs/<int:job_id>/apply', methods=['POST'])
    def job_apply(self, job_id, **kwargs):
        job = self._get_published_job(job_id)
        if kwargs.get('website_hp'):
            # Honeypot tripped: pretend success, create nothing (same
            # convention as the odusite_crm contact form).
            return {'id': 0}
        name = str(kwargs.get('name') or '').strip()
        email = str(kwargs.get('email') or '').strip()
        phone = str(kwargs.get('phone') or '').strip()
        linkedin = str(kwargs.get('linkedin') or '').strip()
        introduction = str(kwargs.get('short_introduction') or '').strip()
        cv = request.httprequest.files.get('cv')

        missing = {field: 'required' for field, value in
                   (('name', name), ('email', email), ('phone', phone)) if not value}
        if cv is None or not cv.filename:
            missing['cv'] = 'required'
        if missing:
            raise ApiError(422, 'validation_error', 'Missing required fields.',
                           {'fields': missing})
        if not email_normalize(email):
            raise ApiError(422, 'validation_error', 'Invalid email address.',
                           {'fields': {'email': 'invalid'}})
        if self._has_recent_application(job, email, phone, linkedin):
            raise ApiError(409, 'already_applied',
                           'An application for this position already exists for this candidate.')

        applicant = request.env['hr.applicant'].sudo().create({
            'partner_name': name,
            'email_from': email,
            'partner_phone': phone,
            'linkedin_profile': linkedin or False,
            'job_id': job.id,
            'company_id': job.company_id.id or False,
        })
        request.env['ir.attachment'].sudo().create({
            'name': cv.filename,
            'raw': cv.read(),
            'res_model': 'hr.applicant',
            'res_id': applicant.id,
        })
        if introduction:
            # Mirrors the upstream website form, which logs the free-text
            # introduction in the chatter instead of a field.
            applicant.message_post(
                body=plaintext2html(introduction),
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
        return {'id': applicant.id}
