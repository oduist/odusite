// Route manifest for the "newsletter" block (backed by odusite_mass_mailing).
// The block ships no pages: the subscribe form renders inside the footer
// (src/components/Footer.astro imports it dynamically when the block is on).
export default {
  routes: [
    { pattern: '/api/newsletter/subscribe', entrypoint: 'api/subscribe.ts' },
  ],
};
