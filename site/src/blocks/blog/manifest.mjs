// Blog block route manifest (see specs/site/01-blocks.md).
// Entrypoints are resolved relative to this directory by integrations/blocks.mjs.
export default {
  routes: [
    { pattern: '/blog', entrypoint: 'pages/index.astro' },
    { pattern: '/blog/feed.xml', entrypoint: 'pages/feed.xml.ts' },
    { pattern: '/blog/[slug]', entrypoint: 'pages/post.astro' },
  ],
};
