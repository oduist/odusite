---
hide:
  - navigation
  - toc
---

<section class="odu-hero">
  <span class="odu-hero__eyebrow">◆ Headless Odoo · Astro on Cloudflare</span>
  <h1 class="odu-hero__title">Odusite Docs</h1>
  <p class="odu-hero__subtitle">
    The entire public website and customer portal of <strong>Odoo 19</strong>,
    re-created as a fast, modular, themable <strong>Astro</strong> site on
    Cloudflare Workers. Odoo stays the backend — a headless CMS reached only
    through a token-secured REST API.
  </p>
  <div class="odu-hero__actions">
    <a class="odu-btn odu-btn--primary" href="architecture/">How it works →</a>
    <a class="odu-btn odu-btn--ghost" href="admin/installation/">Install Guide</a>
    <a class="odu-btn odu-btn--ghost" href="https://github.com/oduist/odusite">View on GitHub</a>
  </div>
</section>

<div class="grid cards" markdown>

-   :material-shield-key-outline:{ .lg .middle } **Token-secured REST API**

    ---

    The browser never talks to Odoo. The Astro Worker calls `/odusite/v1/...`
    server-to-server, authenticated with the `X-Odusite-Token` header.

    [:octicons-arrow-right-24: Architecture](architecture.md)

-   :material-view-grid-plus-outline:{ .lg .middle } **Modular Blocks**

    ---

    Blog, shop, portal, events, jobs, forum, courses and more — each a
    build-time block that a disabled site ships zero JS and zero routes for.

    [:octicons-arrow-right-24: Site Blocks](admin/blocks.md)

-   :material-palette-outline:{ .lg .middle } **Themable by Tokens**

    ---

    Every colour and spacing flows through the theme layer's design tokens.
    Default theme is a polished dark theme; swap it without touching blocks.

    [:octicons-arrow-right-24: Configuration](admin/configuration.md)

-   :material-cart-outline:{ .lg .middle } **Headless Commerce**

    ---

    Catalog, cart and checkout run against a draft `sale.order`. Payments go
    straight to the provider (Stripe first); Odoo stays the source of truth.

    [:octicons-arrow-right-24: Shopping](user/shopping.md)

-   :material-account-circle-outline:{ .lg .middle } **JWT Portal**

    ---

    Sign-up with email double opt-in, orders, quotations, invoices and
    projects — all behind short-lived JWTs issued by Odoo. No session cookies.

    [:octicons-arrow-right-24: Customer Portal](user/portal.md)

-   :material-cloud-upload-outline:{ .lg .middle } **Edge-cached SSR**

    ---

    Marketing pages prerender at the edge; catalog, cart and portal render on
    demand. Odoo webhooks invalidate exactly the pages that changed.

    [:octicons-arrow-right-24: Site Deployment](admin/site-deploy.md)

</div>

## What Odusite is

Odusite re-creates the Odoo 19.0 public website and customer portal as a
standalone [Astro](https://astro.build) site deployed on Cloudflare Workers,
with Odoo acting as a headless CMS/backend. Odoo's own rendering — QWeb,
website snippets, the website builder — is **not** used. Everything the visitor
sees is authored and served by the Astro frontend.

The two halves talk over a single, deliberate seam:

- **`addons/odusite_*`** — Odoo 19 addons. Each depends on a standard module
  (`sale`, `website_blog`, `crm`, …) and exposes REST controllers under
  `/odusite/v1/...`. Everything shared — token check, JSON envelope,
  pagination, image URLs, webhooks — lives in `odusite_base`.
- **`site/`** — the Astro frontend: hybrid SSR on Cloudflare Workers, grouped
  into build-time **blocks** and styled entirely through a **theme** layer.

Every request from the site to Odoo carries `X-Odusite-Token`; portal actions
add a user JWT in `Authorization: Bearer`. Public reads are filtered exactly
like the stock website controllers (`is_published`, multi-website domain,
publish date), so no unpublished record ever leaks.

## Start here

<div class="grid cards" markdown>

-   :material-map-outline:{ .lg .middle } **Understand the system**

    ---

    Read the [Architecture](architecture.md) overview, then dive into the
    specs in the repository for full detail.

-   :material-rocket-launch-outline:{ .lg .middle } **Run it yourself**

    ---

    [Install the Odoo addons](admin/installation.md), then
    [deploy the Astro site](admin/site-deploy.md) to Cloudflare.

-   :material-book-open-page-variant-outline:{ .lg .middle } **Use the site**

    ---

    The [User Guide](user/README.md) walks through the account, shop, portal
    and community features from a visitor's point of view.

</div>
