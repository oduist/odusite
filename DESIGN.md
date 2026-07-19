# Design

Visual system for the Odusite `default` theme. It maps onto the existing token
contract in `site/src/themes/default/tokens.css` (the `--od-*` variables and
`specs/site/02-theming.md`), so shipping it is a clean token swap plus one
self-hosted display face. All colors are given as design-intent OKLCH and as the
verified sRGB hex to write into tokens.

## Theme

- **Name:** default
- **Base:** light
- **World / named reference:** *bright editorial — near-white paper, near-black
  ink, one bold scarlet.* A crisp near-white surface, near-black ink, and a single
  scarlet accent that carries the brand. High-contrast and light. The felt
  reference is a well-set printed page: black type on bright stock with a red
  signal, rendered as a fast light UI.
- **Color strategy:** Restrained-with-a-loud-accent. The bright paper + black ink
  do the reading; one scarlet carries all the brand energy (primary actions, the
  accent word, links). Neutrals carry a whisper of the scarlet hue, never a
  UI-kit gray or a default cream.

## Color

OKLCH is the design source of truth; the hex is the sRGB value to write into
`tokens.css`. Neutrals carry a whisper of the scarlet hue (not default warmth),
and the accent is the one place chroma spikes.

### Surfaces (bright paper; cards a touch brighter than the page)

| Token | OKLCH (intent) | Hex | Role |
|---|---|---|---|
| `--od-bg` | 0.96 0.004 40 | `#f5f2ef` | page base, bright paper |
| `--od-bg-raised` | 0.995 0.003 80 | `#fffefc` | cards, header, panels |
| `--od-bg-inset` | 0.92 0.006 45 | `#eae4df` | wells, media placeholders |
| `--od-bg-hover` | 0.94 0.005 45 | `#efe9e3` | hover surface, footer floor |

### Text (near-black ink)

| Token | OKLCH | Hex | Contrast on `--od-bg` |
|---|---|---|---|
| `--od-fg` | 0.20 0.010 40 | `#1a1512` | 16.2:1 |
| `--od-fg-muted` | 0.44 0.012 55 | `#5a524c` | 6.9:1 (body-safe) |
| `--od-fg-subtle` | 0.51 0.013 55 | `#6d635b` | 5.3:1 (still AA body) |

`--od-fg-muted` is the default body/paragraph color. `--od-fg-subtle` is for meta
only but is kept above 4.5:1 deliberately, so no essential text falls below AA.

### Accent (bold scarlet)

| Token | OKLCH | Hex | Note |
|---|---|---|---|
| `--od-accent` | 0.58 0.205 28 | `#d42817` | links, primary fill, focus — 4.6:1 on bg |
| `--od-accent-hover` | 0.51 0.205 30 | `#b31f10` | hover |
| `--od-accent-active` | 0.46 0.200 30 | `#9e1a0d` | active |
| `--od-accent-fg` | 1.0 0 0 | `#ffffff` | white on scarlet fill — 5.1:1 on accent |
| `--od-accent-soft` | — | `rgba(212,40,23,0.1)` | soft tint fills |

Scarlet is bold, so it carries the brand energy on a quiet ground. Keep the
*large* fills to genuine primary actions (the button, one accent word, focus,
links); do not chip every noun in red.

### Semantic (readable on the bright paper)

| Token | Hex | Note |
|---|---|---|
| `--od-success` | `#1f9d55` | green |
| `--od-warning` | `#b9770c` | amber/gold, darkened to read on light |
| `--od-danger` | `#c0261a` | deep red (a touch deeper than the brand scarlet) |
| `--od-info` | `#0e8a9e` | teal — semantic state only, never a surface |

Each keeps its `-soft` rgba tint at ~0.12 alpha.

### Borders (light self-colored edges)

| Token | Hex |
|---|---|
| `--od-border` | `#e4ddd6` |
| `--od-border-strong` | `#d3cac2` |

Low-contrast light edges shifted off the surface's own value: an edge you sense as
a lip, not a hard contrasting hairline.

## Typography

Voice words: **editorial, confident, alive** (physical-object words: a hand-set
title page, black type on bright stock with a red signal). The reflex reach would be
Fraunces/Playfair/Cormorant — all rejected as training-data defaults and as the
editorial-magazine lane. Reach further for character. A characterful serif in
near-black ink on bright paper, with one scarlet accent, is the whole voice:
editorial poise, one loud signal.

- **Display — `--od-font-display`: "Gambarino"** (Fontshare, free, self-hosted
  woff2 subset). A characterful editorial serif with real personality that is not
  on any reflex-reject list. Used for `h1`/`h2`, the hero, the wordmark and
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
  step (`--od-bg-raised` over `--od-bg`) plus the light 1px border. Avoid the
  symmetric black bloom.
- If a shadow is genuinely needed (a floating menu, the payment sheet), make it
  tight, low-offset and **soft ink-tinted** (see `--od-shadow-*`), never a heavy
  black halo.
- One **bespoke silhouette** signs the brand surfaces (a chamfer, a notch, a
  cut/dog-eared corner) — used once, deliberately, not on every box.

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

- **Button** (`components/themeable/Button.astro`): primary = solid scarlet fill
  with a white label (verified 5.1:1); no glow, no lift. Hover shifts
  the fill tonally / slides an icon. Do **not** ship a filled-primary + outlined-
  secondary pair as the default action row: use one clear action, and if a second
  is needed differentiate it by weight/placement, not a ghost outline.
- **Card** (`Card.astro`): light self-colored border + tonal border-hover (as
  today). Never stack every tell into one card (icon tile + pill + tags + glow).
- **Badge** (`Badge.astro`): stop rendering a tinted uppercase-tracked pill around
  *every* tag (see `PostCard`). Reserve the chip for genuine status; rank ordinary
  metadata with type weight and color instead.
- **Hero** (`Hero.astro`): replace the centered eyebrow→title→subtitle→two-buttons
  stack with a composed frame — one signature artifact, directional atmosphere
  (grain / raked scarlet light, not a radial accent blob), layered depth.
- **Header/nav** (`Header.astro`): treat the nav (contain it, give the brand real
  presence), don't leave a flush row of links. Keep active state as a color/weight
  shift (already correct), never a dot.
- **Footer** (`Footer.astro`): give it one idea — an oversized Gambarino wordmark
  anchored flush to the bottom edge over a grained paper substrate — not the
  standard brand + 3 ruled link columns + colophon.

## Imagery

Brand register requires real imagery; a flat fill where a hero visual belongs is a
bug. The framework already renders real Odoo entities (products, post covers,
avatars) — lean on those as the populated artifact. The demo homepage hero should
carry a real, populated product/portal UI (floated, clipped at an edge) or an
editorial scene, never a colored placeholder box. Decorative hero plates render
their image in editorial black-and-white (with a whisper of scarlet) so any source
image, including Odoo's flat colour placeholders, coheres on the bright ground; the
real catalog imagery stays untouched. Alt text is part of the voice.

## Anti-slop guardrails (keep these out)

Cool blue-charcoal surfaces or a violet/periwinkle accent · blue→purple or pastel
gradients · gradient text (`background-clip:text`) · glowy pill buttons and inner-
glow badges · side-stripe (`border-left`) accents · the SaaS meta-skeleton stack ·
tiny uppercase tracked eyebrow above every section · numbered `01/02/03` section
markers by reflex · tinted-pill chips on every label · fake app-window mockups ·
identical endless card grids · the filled+outlined button pair · Fraunces/Playfair/
Inter/Space-Grotesk and the Google reflex shelf · cream/beige "editorial" bg ·
sun-moon theme toggle. When about to write one, rewrite the element instead.
