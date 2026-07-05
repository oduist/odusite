// Shop block route manifest (specs/site/01-blocks.md).
// Entrypoints are relative to this directory; the odusiteBlocks()
// integration injects them when the block is enabled.
export default {
  routes: [
    // Catalog
    { pattern: '/shop', entrypoint: 'pages/index.astro' },
    { pattern: '/shop/category/[slug]', entrypoint: 'pages/category.astro' },
    { pattern: '/shop/[slug]', entrypoint: 'pages/product.astro' },
    // Cart & checkout
    { pattern: '/cart', entrypoint: 'pages/cart.astro' },
    { pattern: '/checkout', entrypoint: 'pages/checkout.astro' },
    { pattern: '/checkout/confirmation', entrypoint: 'pages/confirmation.astro' },
    // Same-origin endpoints for browser islands (proxy to Odoo via apiFetch)
    { pattern: '/api/shop/cart/add', entrypoint: 'api/cart-add.ts' },
    { pattern: '/api/shop/cart/update', entrypoint: 'api/cart-update.ts' },
    { pattern: '/api/shop/checkout/address', entrypoint: 'api/checkout-address.ts' },
    { pattern: '/api/shop/checkout/delivery', entrypoint: 'api/checkout-delivery.ts' },
    { pattern: '/api/shop/combination', entrypoint: 'api/combination.ts' },
  ],
};
