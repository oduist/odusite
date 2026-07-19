# Product

## Register

brand

## Users

Two audiences share one surface:

- **Evaluators of the framework** (primary): Odoo developers, agencies and
  technical decision-makers deciding whether to adopt Odusite (Odoo as a headless
  CMS behind an Astro/Cloudflare frontend). They arrive to judge whether the
  framework produces real, fast, distinctive sites. For them the demo *is* the
  pitch: they read the framework's craft off the demo's craft.
- **End users of a live deployment** (secondary): shoppers, blog readers and
  portal customers of any real site built on this theme. The same `default` theme
  chrome serves them, so it must stay legible, calm and reusable, not a one-off
  art piece.

Context: a fast evaluative first impression on the marketing surfaces (home,
content pages), then real transactional work on the product surfaces (shop,
cart, checkout, portal, forum, courses).

## Product Purpose

Odusite re-creates an Odoo 19 public website and customer portal as a standalone
Astro site on Cloudflare Workers, with Odoo acting purely as a headless backend.
The `default` theme is the reference/showcase theme for that framework.

Its job is twofold and in tension, which is the whole design problem:

1. **Sell the framework.** Prove that Odusite yields a site a visitor would call
   crafted, not generated. The bar: someone asks "how was this made?", never
   "which AI made this?".
2. **Stay a reusable base.** Other deployments inherit this theme and override it
   through the theme layer (`site/src/themes/<name>/`, design tokens). So the
   identity must live in a small, swappable system (palette + one display face),
   not in loud per-page art that fights every tenant's brand.

Success = the theme reads as *deliberately chosen* rather than defaulted, while
remaining clean enough that a second brand can re-skin it by editing tokens.

## Brand Personality

**Warm, editorial, human.** Voice: plain and specific, confident without hype;
it names what the product literally does. Emotional goal: the sense that people
who care about detail made this. Warmth and humanity are the differentiators
against the cold, template feel of most Odoo-adjacent and headless-CMS demos.

## Anti-references

- **The cool blue-charcoal / slate-indigo "serious dark SaaS" default** — which
  is exactly what the current theme is (`theme.json` self-describes as
  "near-black blue-tinted surfaces, single violet-blue accent, system fonts").
  This is the single loudest tell to leave behind.
- **The generic SaaS product-page meta-skeleton**: two-column hero with a panel
  on the right, a row of three icon-in-a-tile feature cards, three pricing tiers,
  an FAQ accordion, a full-width gradient CTA slab, a multi-column ruled footer.
- **The editorial-magazine reflex lane**: high-contrast Didone/old-style serif
  (Fraunces, Playfair, Cormorant, Newsreader) + italic accent word + small mono
  labels + ruled columns. The brief is warm and editorial, but it must not become
  a Klim-clone specimen page. Warmth comes from a *humanist* face, not a costume.
- Cream/beige "tasteful premium" backgrounds; blue-to-purple gradients; glowy
  pill buttons; gradient text; tinted-pill chips around every label; the
  sun/moon theme toggle; fake app-window mockups.

## Design Principles

1. **The demo is the evidence.** Every screen is a working proof that the
   framework produces craft. No filler, no fake data, no invented logos: show the
   real products, posts and portal the framework actually renders.
2. **Identity lives in the system, not the decoration.** One chosen palette and
   one display face, carried through the existing `--od-*` tokens, do the
   brand work. That keeps the theme reusable: a tenant re-skins by swapping
   tokens, not by fighting bespoke per-page art.
3. **Carry warmth in type, color and copy, not in gimmicks.** Warmth is not a
   warm-tinted near-white background or a decorative glow; it is the surface hue,
   the display face and specific, human copy.
4. **Reusable, yet unmistakably chosen.** Neutral enough for many tenants to
   inherit, opinionated enough that no one reads it as an off-the-shelf default.
5. **Clean is the floor.** A correct, calm page with zero authored moments is
   unfinished. Every key surface earns at least one deliberate, purposeful detail
   (a composed hero, a treated nav, an authored hover), never motion for its own
   sake.

## Accessibility & Inclusion

- **WCAG AA** as the working target: body text ≥ 4.5:1, large/UI text ≥ 3:1,
  against its actual background. The default palette is contrast-verified against
  this bar (see DESIGN.md).
- `prefers-reduced-motion` is honored on every animation (crossfade or instant
  fallback); it is already respected globally and must stay that way.
- **Content is visible by default.** Never gate the existence of text or a control
  on an entrance animation completing.
- Visible keyboard focus; semantic markup; link and button labels that carry
  standalone meaning.
- No hard AAA mandate, but push contrast toward the ink end when a value is close
  rather than chasing "elegant" light gray.
