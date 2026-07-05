// Route manifest for the "courses" block (see specs/site/01-blocks.md).
// Entrypoints are resolved relative to this directory by integrations/blocks.mjs.
export default {
  routes: [
    { pattern: '/courses', entrypoint: 'pages/index.astro' },
    { pattern: '/courses/[slug]', entrypoint: 'pages/[slug]/index.astro' },
    { pattern: '/courses/[slug]/[slide]', entrypoint: 'pages/[slug]/[slide].astro' },
    { pattern: '/api/courses/join', entrypoint: 'api/join.ts' },
    { pattern: '/api/courses/complete', entrypoint: 'api/complete.ts' },
    { pattern: '/api/courses/quiz', entrypoint: 'api/quiz.ts' },
    { pattern: '/api/courses/binary/[courseId]/[slideId]', entrypoint: 'api/binary/[courseId]/[slideId].ts' },
  ],
};
