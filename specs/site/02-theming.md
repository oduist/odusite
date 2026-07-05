# Astro Site — Theming

## Model

A theme = design tokens + optional component overrides.
Location: `src/themes/<name>/`. Selected at build
(`odusite.config.mjs` / `ODUSITE_THEME`).

```
src/themes/default/
  theme.json          metadata (name, dark/light base, font stacks)
  tokens.css          CSS custom properties (the ONLY source of visual values)
  global.css          base element styles (typography, links, focus rings)
  components/         optional .astro overrides (same filename ⇒ replaces core)
```

## Tokens (contract, all `--od-*`)

- Color: `--od-bg`, `--od-bg-raised`, `--od-bg-inset`, `--od-fg`,
  `--od-fg-muted`, `--od-fg-subtle`, `--od-accent`, `--od-accent-fg`,
  `--od-accent-hover`, `--od-border`, `--od-border-strong`,
  semantic: `--od-success`, `--od-warning`, `--od-danger`, `--od-info`.
- Typography: `--od-font-sans`, `--od-font-mono`, `--od-text-{xs..3xl}`,
  `--od-leading`, `--od-tracking-wide`.
- Shape/space: `--od-radius-{s,m,l,full}`, `--od-space-{1..10}` (4px scale),
  `--od-shadow-{s,m,l}`, `--od-container` (max width).
- Motion: `--od-ease`, `--od-dur-{fast,base,slow}`.

Rules: block/core components use tokens exclusively (no raw hex/px for visual
identity); layout math (grid gaps etc.) may use space tokens; every
interactive element has visible `:focus-visible`; color contrast ≥ WCAG AA.

## Component override resolution

Vite alias `@theme/*` → tries `src/themes/<active>/components/*`, falls back
to `src/components/themeable/*`. Core themeable set: Button, Card, Badge,
Input/Select/Checkbox, Hero, PriceTag, EmptyState, Skeleton, Toast.

## Theme `default` (v1)

Dark, restrained, "developer-grade" aesthetic:
- near-black blue-tinted background (`#0b0e14` family), raised surfaces via
  subtle lightness steps — no pure black, no pure white text (`#e6e9ef`);
- single accent (violet-blue ~`#7c86ff` family) + its hover/active ramp;
- system font stack with `Inter`-like metrics (no webfont in v1 — zero CLS),
  mono for prices/order refs;
- 1px borders (`#232838` family) over shadows; shadows only for overlays;
- radius m=10px; generous whitespace; max container 1200px;
- motion: 150–250ms ease-out, respects `prefers-reduced-motion`;
- light-mode counterpart deferred (tokens ready, `data-theme` attribute).
