# Site blocks

Functionality on the site is grouped into blocks, activated at build time
(`site/odusite.config.mjs` or `ODUSITE_BLOCK_*` env). Each block needs its
Odoo addon installed.

| Block | Site routes | Odoo addon | Extra configuration |
|---|---|---|---|
| forms | `/contact` | odusite_crm | Optional Turnstile keys (site env). Leads land in CRM with UTM attribution. |
| newsletter | footer form (no pages) | odusite_mass_mailing | Subscribes to the first public mailing list (Email Marketing → Mailing Lists, "Show In Preferences"). Honeypot anti-spam only. |
| blog | `/blog`, `/blog/<post>`, `/blog/feed.xml` | odusite_blog | Publish posts in Odoo Website → Blog. |
| shop | `/shop`, `/shop/<product>`, `/cart`, `/checkout` | odusite_sale + odusite_payment | Publish products, set pricelists on the website, configure delivery methods (published ones appear at checkout) and a payment provider. |
| portal | `/login`, `/signup`, `/portal/*` | odusite_portal (+ odusite_account, odusite_project, odusite_sale for the sections) | Portal sections appear only for installed addons/enabled blocks. |
| events | `/events`, `/events/<event>` | odusite_event | Publish events; free tickets only in phase 1. |
| jobs | `/jobs`, `/jobs/<job>` | odusite_hr_recruitment | Publish job positions; applications become candidates with the CV attached. |
| partners | `/partners`, `/partners/<partner>` | odusite_partner | Publish partner contacts; grades/references appear when website_crm_partner_assign is installed. |
| forum | `/forum/*` | odusite_forum | Off by default. Posting/voting requires portal login; karma rules apply as in Odoo. |
| courses | `/courses/*` | odusite_slides | Off by default. Public courses joinable by logged-in users; paid courses — phase 2. |

`/search` is part of the core (not a block): it is powered by Odoo's unified
website search via `odusite_base` and only shows result types whose block is
enabled.

## Navigation

The main menu is defined in `odusite.config.mjs` (`nav`) — entries bound to a
disabled block disappear automatically. Odoo's website menu is also available
to the site through the API (`/odusite/v1/menus`) for menu-driven setups.

## Theming

The active theme is set at build time (`ODUSITE_THEME`, default `default` —
dark). Themes live in `site/src/themes/<name>/`: design tokens + optional
component overrides. See `specs/site/02-theming.md` for the authoring guide.
