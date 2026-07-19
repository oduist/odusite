# Design

Visual system for the Odusite `default` theme. This is the *target* direction
(deliberately-chosen warm-dark editorial), not a record of the current cool-blue
default. It maps onto the existing token contract in
`site/src/themes/default/tokens.css` (the `--od-*` variables and
`specs/site/02-theming.md`), so shipping it is a clean token swap plus one
self-hosted display face. All colors are given as design-intent OKLCH and as the
verified sRGB hex to write into tokens.

## Theme

- **Name:** default
- **Base:** dark
- **World / named reference:** *oxblood book-cloth on warm ink, terracotta ember.*
  A warm near-black surface tinted toward oxblood (deep wine-brown), warm
  off-white ink, and a single terracotta/clay accent. The felt reference is a
  cloth-bound letterpress edition read by lamplight, rendered as a fast dark UI,
  not a magazine specimen page.
- **Color strategy:** Committed-restrained. The warm oxblood *surface* carries the
  brand (committed); one terracotta accent + warm tinted neutrals do the rest
  (restrained), so the theme stays reusable.

## Color

OKLCH is the design source of truth; the hex is the sRGB value to write into
`tokens.css`. Every neutral is tinted toward the oxblood hue (~30–35°), never
toward blue and never a true gray.

### Surfaces

| Token | OKLCH (intent) | Hex | Role |
|---|---|---|---|
| `--od-bg` | 0.17 0.020 32 | `#17100e` | page base, warm oxblood-black |
| `--od-bg-raised` | 0.21 0.024 32 | `#211613` | cards, header, panels |
| `--od-bg-inset` | 0.14 0.018 32 | `#120b0a` | wells, media placeholders, footer floor |
| `--od-bg-hover` | 0.26 0.028 32 | `#2a1c18` | hover surface, neutral chip |

### Text (warm off-white, warmth carried here)

| Token | OKLCH | Hex | Contrast on `--od-bg` |
|---|---|---|---|
| `--od-fg` | 0.94 0.008 70 | `#f2ece6` | 16.0:1 |
| `--od-fg-muted` | 0.74 0.014 55 | `#b6a69c` | 8.0:1 (body-safe) |
| `--od-fg-subtle` | 0.58 0.015 45 | `#8a7a70` | 4.6:1 (still AA body) |

`--od-fg-muted` is the default body/paragraph color and clears 4.5:1 on both the
base and raised surfaces (8.0 / 7.5). `--od-fg-subtle` is for meta only but is
kept above 4.5:1 deliberately, so no essential text ever falls below AA.

### Accent (terracotta / clay ember)

| Token | OKLCH | Hex | Note |
|---|---|---|---|
| `--od-accent` | 0.70 0.130 42 | `#d9744f` | links, primary fill, focus — 5.9:1 on bg |
| `--od-accent-hover` | 0.76 0.125 45 | `#e79070` | hover |
| `--od-accent-active` | 0.64 0.130 40 | `#c15f3d` | active |
| `--od-accent-fg` | 0.20 0.030 35 | `#241612` | ink on accent fill — 5.5:1 on accent |
| `--od-accent-soft` | — | `rgba(217,116,79,0.14)` | soft tint fills |

The accent is analogous to the oxblood surface (cohesion), lighter and more
saturated so it reads as a considered tint, not a sprayed highlight. Use it
**sparingly and tonally**: one accent per view, not on every dot, label and
button at once.

### Semantic (kept distinct from the terracotta brand accent)

| Token | Hex | Hue keeps clear of accent by |
|---|---|---|
| `--od-success` | `#74be6e` | green (145°) |
| `--od-warning` | `#e0b13a` | gold (78°) |
| `--od-danger` | `#e2564a` | crimson, higher chroma & redder (25°) than terracotta |
| `--od-info` | `#5aa9d6` | muted sky — semantic only, never a surface |

Each keeps its `-soft` rgba tint at ~0.12 alpha, as today. `--od-info` blue is
allowed *only* as a semantic state; it must never become a surface or the theme
regresses toward the blue-charcoal it is leaving.

### Borders (self-colored warm, felt not drawn)

| Token | Hex |
|---|---|
| `--od-border` | `#33231e` |
| `--od-border-strong` | `#45312a` |

Low-contrast warm edges shifted off the surface's own hue: an edge you sense as a
lip catching light, not a hard contrasting hairline.

## Typography

Voice words: **warm, editorial, human** (physical-object words: a cloth-bound
book, a letterpress colophon, a hand-set title page). The reflex reach would be
Fraunces/Playfair/Cormorant — all rejected as training-data defaults and as the
editorial-magazine lane. Reach further for a *humanist* warmth.

- **Display — `--od-font-display`: "Gambarino"** (Fontshare, free, self-hosted
  woff2 subset). A warm, characterful editorial serif with real personality that
  is not on any reflex-reject list. Used for `h1`/`h2`, the hero, the wordmark and
  oversized footer type. Set large with `clamp()`, tracking ≥ -0.01em (serifs
  need air; never crush them).
- **Body — `--od-font-sans`: keep the system stack** (`ui-sans-serif,
  -apple-system, 'Segoe UI', Roboto, …`). System-ui is genuinely neutral, honest,
  and free of network cost — the right quiet partner for a distinctive display
  face, and the right call for a theme that must load fast on the edge.
- **Mono — `--od-font-mono`: keep the system mono stack.** Reserved for genuine
  data: prices, order numbers, codes, timestamps. Never the house voice.

Only one self-hosted family is added. Two families total (display serif + system
sans) + a system mono for data. Scale keeps the existing `--od-text-*` steps
(ratio ≥1.25); add a fluid display step for the demo hero:
`--od-text-display: clamp(2.5rem, 6vw, 4.5rem)` (max stays ≤ 6rem). On dark,
headings get +0.05 line-height. Use `text-wrap: balance` on `h1`–`h3`,
`text-wrap: pretty` on prose; cap prose at 65–75ch.

## Layout & Spacing

- Keep the 4px space scale and `--od-container: 1200px`.
- Vary rhythm: generous separation between movements, tight grouping within.
  Introduce fluid section padding with `clamp()` on brand surfaces so it breathes
  on large viewports.
- Responsive grids without breakpoints: `repeat(auto-fit, minmax(280px, 1fr))`.
  Do not reach for identical card grids where real hierarchy would read better.
- Asymmetry is allowed on the demo marketing surfaces when it serves emphasis;
  the product surfaces (portal, checkout) stay calm and aligned.

## Shape & Elevation

- Radii keep the existing scale (`--od-radius-s/m/l/full` = 6/10/16/999px).
- **Elevation from tone + self-colored edge, not shadow.** Panels lift by a value
  step (`--od-bg-raised` over `--od-bg`) plus the warm 1px border. Avoid the
  symmetric black bloom.
- If a shadow is genuinely needed (a floating menu, the payment sheet), make it
  tight, low-offset and **tinted warm** (toward `--od-bg-inset`), never a big
  black halo. Fix the existing `--od-shadow-md` typo (token is `--od-shadow-m`).
- One **bespoke silhouette** signs the brand surfaces (a chamfer, a notch, a
  torn/deckled edge evoking the book-cloth reference) — used once, deliberately,
  not on every box.

## Motion

- Quiet and authored. Add **Motion** (`motion.dev`, `motion/react`; works without
  Tailwind) only where it earns its place: the demo hero settling in, the nav
  entering, a scroll-linked parallax on the signature artifact, tuned hovers.
- **Bans:** hover-boop (button lift/scale), underline-fill/grow, uniform
  fade-and-translate on every section.
- Ease out with exponential curves; no bounce/elastic. Every animation ships a
  `prefers-reduced-motion` crossfade/instant fallback. Never gate content
  visibility on a reveal.

## Components (how the themeable atoms should read)

- **Button** (`components/themeable/Button.astro`): primary = solid terracotta
  fill with the dark ink label (verified 5.5:1); no glow, no lift. Hover shifts
  the fill tonally / slides an icon. Do **not** ship a filled-primary + outlined-
  secondary pair as the default action row: use one clear action, and if a second
  is needed differentiate it by weight/placement, not a ghost outline.
- **Card** (`Card.astro`): warm self-colored border + tonal border-hover (as
  today). Never stack every tell into one card (icon tile + pill + tags + glow).
- **Badge** (`Badge.astro`): stop rendering a tinted uppercase-tracked pill around
  *every* tag (see `PostCard`). Reserve the chip for genuine status; rank ordinary
  metadata with type weight and color instead.
- **Hero** (`Hero.astro`): replace the centered eyebrow→title→subtitle→two-buttons
  stack with a composed frame — one signature artifact, warm directional
  atmosphere (grain / raked light, not a radial accent blob), layered depth.
- **Header/nav** (`Header.astro`): treat the nav (contain it, give the brand real
  presence), don't leave a flush row of links. Keep active state as a color/weight
  shift (already correct), never a dot.
- **Footer** (`Footer.astro`): give it one idea — an oversized warm Gambarino
  wordmark anchored flush to the bottom edge over a warm grained substrate — not
  the standard brand + 3 ruled link columns + colophon.

## Imagery

Brand register requires real imagery; a flat fill where a hero visual belongs is a
bug. The framework already renders real Odoo entities (products, post covers,
avatars) — lean on those as the populated artifact. The demo homepage hero should
carry a real, populated product/portal UI (floated, clipped at an edge) or a warm
editorial scene, never a colored placeholder box. Alt text is part of the voice.

## Anti-slop guardrails (keep these out)

Cool blue-charcoal surfaces or a violet/periwinkle accent · blue→purple or pastel
gradients · gradient text (`background-clip:text`) · glowy pill buttons and inner-
glow badges · side-stripe (`border-left`) accents · the SaaS meta-skeleton stack ·
tiny uppercase tracked eyebrow above every section · numbered `01/02/03` section
markers by reflex · tinted-pill chips on every label · fake app-window mockups ·
identical endless card grids · the filled+outlined button pair · Fraunces/Playfair/
Inter/Space-Grotesk and the Google reflex shelf · cream/beige "editorial" bg ·
sun-moon theme toggle. When about to write one, rewrite the element instead.
