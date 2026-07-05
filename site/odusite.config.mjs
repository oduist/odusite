// Build-time Odusite configuration: blocks, theme, navigation.
// Env overrides: ODUSITE_BLOCK_<NAME>=1|0, ODUSITE_THEME=<name>.

/** @type {import('./integrations/types').OdusiteConfig} */
export default {
  theme: 'default',
  blocks: {
    forms: true,
    newsletter: true,
    blog: true,
    shop: true,
    portal: true,
    events: true,
    jobs: true,
    partners: true,
    forum: false,
    courses: false,
  },
  // Ordered main navigation. `block` entries render only when the block is on.
  nav: [
    { label: 'Shop', href: '/shop', block: 'shop' },
    { label: 'Blog', href: '/blog', block: 'blog' },
    { label: 'Events', href: '/events', block: 'events' },
    { label: 'Jobs', href: '/jobs', block: 'jobs' },
    { label: 'Partners', href: '/partners', block: 'partners' },
    { label: 'Forum', href: '/forum', block: 'forum' },
    { label: 'Courses', href: '/courses', block: 'courses' },
    { label: 'Contact', href: '/contact', block: 'forms' },
  ],
};
