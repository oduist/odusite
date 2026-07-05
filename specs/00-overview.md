# Odusite — Overview

## Goal

Fully re-create the public website and customer portal of Odoo 19.0 as a standalone
Astro site (deployed on Cloudflare Workers), with Odoo acting as a headless
CMS/backend. Odoo website/portal functionality is reproduced module by module,
in a flexible, switchable way.

## System components

1. **`addons/odusite_*`** — Odoo addons. Each one depends on a standard module
   (crm, sale, website_blog, …) and adds REST controllers under `/odusite/v1/...`.
   Odoo rendering (QWeb, snippets) is not used.
2. **`site/`** — the Astro site: hybrid SSR on Cloudflare Workers, modular "blocks"
   (blog, shop, portal, events, …) activated at build time, themable
   (default theme — dark `default`).
3. **`specs/`** — this specification set; the system is re-creatable from it.
4. **`docs/admin`, `docs/user`** — administrator and end-user documentation.

## Key principles

- All site→Odoo traffic is server-to-server with the `X-Odusite-Token` header
  (value from the `ODUSITE_TOKEN` env var). The browser never talks to Odoo
  directly (the only exception: payment-provider redirects on the PSP side).
- User context (portal) is a JWT in `Authorization: Bearer`, issued by Odoo
  (see `03-auth.md`).
- Public data is filtered exactly like the stock website controllers do:
  `is_published` + multi-website domain + publish date.
- Marketing pages (home, About, landings) live in Astro (content collections);
  Odoo is the source of *entity* data only.
- Functionality ships in phases (see `07-roadmap.md`); each functional area =
  spec + addon + site block + documentation.

## Odoo modules → Odusite mapping

| Area | Odoo modules | Addon | Site block |
|---|---|---|---|
| API core | website, web | odusite_base | (core) |
| Portal, auth | portal, auth_signup | odusite_portal | portal |
| Blog | website_blog | odusite_blog | blog |
| Forms → CRM | website_crm, crm | odusite_crm | forms |
| Shop | website_sale, sale | odusite_sale | shop |
| Payments | payment, account_payment | odusite_payment | shop/portal |
| Invoices | account | odusite_account | portal |
| Projects | project | odusite_project | portal |
| Events | website_event(_track) | odusite_event | events |
| Jobs | website_hr_recruitment | odusite_hr_recruitment | jobs |
| Partners | website_customer, website_crm_partner_assign | odusite_partner | partners |
| Forum | website_forum, website_profile | odusite_forum | forum |
| Courses | website_slides | odusite_slides | courses |
| Newsletter | website_mass_mailing, mass_mailing | odusite_mass_mailing | newsletter |
| Phase 2+ | appointment, helpdesk, knowledge, sale_subscription, sale_renting, sign | — | see roadmap |
