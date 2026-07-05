# Odusite

Odoo 19 as a headless CMS + Astro frontend on Cloudflare Workers.

The public website and customer portal of Odoo are re-created as a fast,
modular, themable Astro site. Odoo stays the backend, exposed through a REST
API (`/odusite/v1/...`) secured with the `X-Odusite-Token` header.

```
addons/      Odoo 19 addons (odusite_base, odusite_sale, odusite_portal, ...)
site/        Astro site: build-time blocks, themes, Cloudflare Worker
specs/       Specifications — the system is re-creatable from them
docs/admin/  Administrator documentation
docs/user/   End-user documentation
```

## Quick start

**Odoo**: add `addons/` to the addons path, install the `odusite_*` modules
you need (`odusite_base` is mandatory), copy the API token from
Website Settings → Odusite. See `docs/admin/installation.md`.

**Site**:

```bash
cd site
pnpm install
echo 'ODUSITE_TOKEN=<token from Odoo>' >> .dev.vars
echo 'ODOO_URL=http://localhost:8069' >> .dev.vars
pnpm dev
```

Deploy: `docs/admin/site-deploy.md`. Architecture: `specs/01-architecture.md`.
Contributor guide: `CLAUDE.md`.
