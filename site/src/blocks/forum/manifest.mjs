// Route manifest for the "forum" block (see specs/site/01-blocks.md).
// Entrypoints are resolved relative to this directory by integrations/blocks.mjs.
export default {
  routes: [
    { pattern: '/forum', entrypoint: 'pages/index.astro' },
    { pattern: '/forum/ask', entrypoint: 'pages/ask.astro' },
    { pattern: '/forum/users/[id]', entrypoint: 'pages/users/[id].astro' },
    { pattern: '/forum/[forum]', entrypoint: 'pages/[forum]/index.astro' },
    { pattern: '/forum/[forum]/[post]', entrypoint: 'pages/[forum]/[post].astro' },
    { pattern: '/api/forum/ask', entrypoint: 'api/ask.ts' },
    { pattern: '/api/forum/answer', entrypoint: 'api/answer.ts' },
    { pattern: '/api/forum/vote', entrypoint: 'api/vote.ts' },
    { pattern: '/api/forum/accept', entrypoint: 'api/accept.ts' },
    { pattern: '/api/forum/comment', entrypoint: 'api/comment.ts' },
    { pattern: '/api/forum/favourite', entrypoint: 'api/favourite.ts' },
  ],
};
