# Installation (Odoo side)

## Requirements

- Odoo 19.0 (Community is sufficient for phase 1), Python ≥ 3.10.
- No extra pip packages are required by the odusite addons.

## Install the addons

1. Add this repository's `addons/` directory to `addons_path`.
2. Update the apps list and install the addons for the functionality you need.
   `odusite_base` is required; everything else is optional:

   | Addon | Enables | Pulls in |
   |---|---|---|
   | odusite_base | API core, webhooks, sitemap | website |
   | odusite_portal | login/JWT, account, chatter | portal, auth_signup |
   | odusite_blog | blog API | website_blog |
   | odusite_crm | contact forms → leads | website_crm |
   | odusite_sale | catalog, cart, checkout, portal orders | website_sale |
   | odusite_payment | headless payments | payment, account_payment |
   | odusite_account | portal invoices | account |
   | odusite_project | portal projects/tasks | project |
   | odusite_event | events + registration | website_event |
   | odusite_hr_recruitment | jobs + applications | website_hr_recruitment |
   | odusite_partner | partner directory | website_partner |
   | odusite_forum | forum API | website_forum |
   | odusite_slides | courses API | website_slides |

3. On install, `odusite_base` generates two system parameters:
   - `odusite.token` — the API shared secret,
   - `odusite.jwt_secret` — the JWT signing key.

## Initial configuration

Open **Website → Configuration → Settings → Odusite** and set:

- **API Token** — copy this value; it becomes `ODUSITE_TOKEN` on the site.
- **Site URL** — public URL of the Astro site (used in portal emails and as
  the webhook target), e.g. `https://www.example.com`.
- **Revalidate Secret** — any long random string; the same value goes to the
  site as `ODUSITE_REVALIDATE_SECRET`.
- **Website** — which Odoo website the API exposes (languages, pricelists,
  published records).

## Verifying

```
curl -H "X-Odusite-Token: <token>" https://<odoo>/odusite/v1/health
→ {"data": {"status": "ok", "version": "19.0.1.0.0"}}
```

Without the header the same URL must return HTTP 401.

## Cron jobs

Two scheduled actions ship with `odusite_base` (both enabled by default):
- *Odusite: send cache invalidation webhooks* — every minute, batches pending
  events to `<site>/api/revalidate`.
- *Odusite: garbage-collect webhook events* — daily cleanup.
