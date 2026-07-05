// Route manifest for the "partners" block (backed by odusite_partner).
// Entrypoints are relative to this directory; loaded at config time by
// integrations/blocks.mjs. See specs/site/01-blocks.md.
export default {
  routes: [
    { pattern: '/partners', entrypoint: 'pages/index.astro' },
    { pattern: '/partners/[slug]', entrypoint: 'pages/partner.astro' },
  ],
};
