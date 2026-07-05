// Portal block route manifest (specs/site/01-blocks.md).
// Document sections contributed by other blocks (orders/quotes ← shop) are
// registered here conditionally, mirroring "portal sections register
// themselves within the portal block" from the spec.
import config from '../../../odusite.config.mjs';

function blockEnabled(name) {
  const override = process.env[`ODUSITE_BLOCK_${name.toUpperCase()}`];
  if (override !== undefined) return override === '1' || override === 'true';
  return Boolean(config.blocks?.[name]);
}

const shop = blockEnabled('shop');

const routes = [
  // Auth pages (public)
  { pattern: '/login', entrypoint: 'pages/login.astro' },
  { pattern: '/signup', entrypoint: 'pages/signup.astro' },
  { pattern: '/reset', entrypoint: 'pages/reset.astro' },
  { pattern: '/reset/[token]', entrypoint: 'pages/reset-token.astro' },
  // Password-reset emails link to /portal/reset/<token> (specs/03-auth.md).
  { pattern: '/portal/reset/[token]', entrypoint: 'pages/reset-token.astro' },

  // Auth endpoints (plain form POST targets)
  { pattern: '/api/auth/login', entrypoint: 'api/auth/login.ts' },
  { pattern: '/api/auth/logout', entrypoint: 'api/auth/logout.ts' },
  { pattern: '/api/auth/signup', entrypoint: 'api/auth/signup.ts' },
  { pattern: '/api/auth/forgot', entrypoint: 'api/auth/forgot.ts' },
  { pattern: '/api/auth/reset', entrypoint: 'api/auth/reset.ts' },

  // Portal core pages
  { pattern: '/portal', entrypoint: 'pages/portal/index.astro' },
  { pattern: '/portal/account', entrypoint: 'pages/portal/account.astro' },
  { pattern: '/portal/addresses', entrypoint: 'pages/portal/addresses.astro' },
  { pattern: '/portal/security', entrypoint: 'pages/portal/security.astro' },

  // Invoices (odusite_account)
  { pattern: '/portal/invoices', entrypoint: 'pages/portal/invoices/index.astro' },
  { pattern: '/portal/invoices/[id]', entrypoint: 'pages/portal/invoices/[id].astro' },

  // Projects & tasks (odusite_project)
  { pattern: '/portal/projects', entrypoint: 'pages/portal/projects.astro' },
  { pattern: '/portal/tasks', entrypoint: 'pages/portal/tasks/index.astro' },
  { pattern: '/portal/tasks/[id]', entrypoint: 'pages/portal/tasks/[id].astro' },

  // Portal core proxy endpoints
  { pattern: '/api/portal/addresses', entrypoint: 'api/portal/addresses.ts' },
  { pattern: '/api/portal/password', entrypoint: 'api/portal/password.ts' },
  { pattern: '/api/portal/sessions', entrypoint: 'api/portal/sessions.ts' },
  { pattern: '/api/portal/chatter', entrypoint: 'api/portal/chatter.ts' },
  { pattern: '/api/portal/invoices/[id]/pdf', entrypoint: 'api/portal/invoices/[id]/pdf.ts' },
];

if (shop) {
  routes.push(
    { pattern: '/portal/orders', entrypoint: 'pages/portal/orders/index.astro' },
    { pattern: '/portal/orders/[id]', entrypoint: 'pages/portal/orders/[id].astro' },
    { pattern: '/portal/quotes', entrypoint: 'pages/portal/quotes.astro' },
    { pattern: '/api/portal/orders/[id]/accept', entrypoint: 'api/portal/orders/[id]/accept.ts' },
    { pattern: '/api/portal/orders/[id]/decline', entrypoint: 'api/portal/orders/[id]/decline.ts' },
    { pattern: '/api/portal/orders/[id]/pdf', entrypoint: 'api/portal/orders/[id]/pdf.ts' },
  );
}

export default { routes };
