# odusite_crm

Depends: `odusite_base`, `website_crm` (brings `crm`). Website forms → leads.

## Endpoints

| Route | Method | Description |
|---|---|---|
| `/odusite/v1/forms/contact` | POST | `{name, email, phone?, company?, subject?, message, meta?: {page, utm_source, utm_medium, utm_campaign}}` → creates `crm.lead` (type=lead, team from website defaults, `medium_id`=Website). Returns `{id}`. 422 on missing required fields. |
| `/odusite/v1/forms/generic/<model>` | POST | Whitelisted generic form endpoint mirroring `/website/form/<model>` for models registered by other odusite modules (e.g. `project.task` in odusite_project). Field whitelist per model (`odusite.form.models` registry: model → allowed fields, required fields, post-processing hook). |

## Anti-spam

- The Worker verifies Turnstile before proxying form POSTs (site-side).
- Odoo side: honeypot field rejection + per-IP throttle (simple
  `ir.config_parameter` window counter) as defense in depth.
- UTM values map to `utm.source/medium/campaign` records (get-or-create).

## Webhooks / sitemap

None (write-only module).

## Site block `forms`

Contact page/section with Turnstile, success/error states; a reusable
`<OdForm>` component (field schema → POST endpoint) used by other blocks
(job application, task submission).
