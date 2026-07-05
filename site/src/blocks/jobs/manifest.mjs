// Route manifest for the "jobs" block (backed by odusite_hr_recruitment).
// Entrypoints are relative to this directory; loaded at config time by
// integrations/blocks.mjs. See specs/site/01-blocks.md.
export default {
  routes: [
    { pattern: '/jobs', entrypoint: 'pages/index.astro' },
    { pattern: '/jobs/[slug]', entrypoint: 'pages/job.astro' },
    { pattern: '/api/jobs/apply', entrypoint: 'api/apply.ts' },
  ],
};
