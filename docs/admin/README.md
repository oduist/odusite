# Odusite — Administrator Documentation

Odusite runs the public website and customer portal as an Astro site on
Cloudflare, with Odoo 19 as the headless backend. This section covers
installation, configuration and operations.

## Contents

- [installation.md](installation.md) — Odoo addons: install and initial setup
- [site-deploy.md](site-deploy.md) — Astro site: build, Cloudflare deploy, env vars
- [topologies.md](topologies.md) — how the Worker reaches Odoo: Cloudflare Tunnel vs public origin
- [configuration.md](configuration.md) — Odoo settings, tokens, webhooks, languages
- [payments.md](payments.md) — payment providers (Stripe first)
- [blocks.md](blocks.md) — enabling/disabling site blocks and what each requires
- [voice-assistant.md](voice-assistant.md) — optional ElevenLabs voice navigation
- [s3.md](s3.md) — offloading the attachment filestore to S3 / Cloudflare R2

## Architecture in one paragraph

The browser only ever talks to the Astro site. The site's Cloudflare Worker
calls Odoo's REST API (`/odusite/v1/...`) server-to-server, authenticating with
the `X-Odusite-Token` header. Portal users get JWT tokens issued by Odoo and
stored in site cookies. When content changes in Odoo, a webhook tells the site
to drop the affected cached pages. Payments run directly between the browser
and the payment provider (e.g. Stripe), with Odoo as the source of truth via
provider webhooks.
