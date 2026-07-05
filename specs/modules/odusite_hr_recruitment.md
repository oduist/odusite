# odusite_hr_recruitment

Depends: `odusite_base`, `website_hr_recruitment` (brings `hr_recruitment`).

## Endpoints

| Route | Method | Description |
|---|---|---|
| `/odusite/v1/jobs` | GET | Paginated published `hr.job`. Filters: `?department=&country=&employment_type=&remote=&search=`. Item: `{id, slug, name, department, location: {city, country}, employment_type, is_remote, published_date}`. `meta.facets`: departments/locations/types with counts. |
| `/odusite/v1/jobs/<id_or_slug>` | GET | Detail: + `description_html` (website_description + job_details), `seo`. |
| `/odusite/v1/jobs/<id>/apply` | POST | multipart: `{name, email, phone, linkedin?, short_introduction?, cv: file}` → creates `hr.applicant` + attachment (mirrors `/website/form/hr.applicant` whitelist). Duplicate-application check (`check_recent_application` logic) → 409 `already_applied`. |

## Webhooks / sitemap

Watched: `hr.job` (publish, description, name). Tags: `jobs`, `jobs:<id>`.
Sitemap: `/jobs/<slug>`.

## Site block `jobs`

`/jobs` (list + facet filters), `/jobs/[job]` (description, apply form with CV
upload + Turnstile, success state).
