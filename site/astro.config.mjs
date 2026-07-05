// @ts-check
import { defineConfig } from 'astro/config';
import cloudflare from '@astrojs/cloudflare';
import mdx from '@astrojs/mdx';
import { odusiteBlocks } from './integrations/blocks.mjs';

export default defineConfig({
  output: 'server',
  adapter: cloudflare({
    platformProxy: { enabled: true },
    imageService: 'passthrough',
  }),
  integrations: [mdx(), odusiteBlocks()],
  security: {
    checkOrigin: true,
  },
});
