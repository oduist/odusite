// Route manifest for the "forms" block (backed by odusite_crm).
// Entrypoints are relative to this directory; loaded at config time by
// integrations/blocks.mjs. See specs/site/01-blocks.md.
export default {
  routes: [
    { pattern: '/contact', entrypoint: 'pages/contact.astro' },
    { pattern: '/api/forms/contact', entrypoint: 'api/contact.ts' },
  ],
};
