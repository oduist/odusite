// Events block route manifest (see specs/site/01-blocks.md).
// Entrypoints are resolved relative to this directory by integrations/blocks.mjs.
export default {
  routes: [
    { pattern: '/events', entrypoint: 'pages/index.astro' },
    { pattern: '/events/[slug]', entrypoint: 'pages/event.astro' },
    { pattern: '/api/events/register', entrypoint: 'api/register.ts' },
    { pattern: '/api/events/[id]/ics', entrypoint: 'api/ics.ts' },
  ],
};
