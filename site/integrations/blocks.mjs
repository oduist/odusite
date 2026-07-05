// Odusite blocks integration: build-time block activation, theme alias,
// virtual config module. See specs/site/01-blocks.md.
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const VIRTUAL_ID = 'virtual:odusite/config';
const RESOLVED_VIRTUAL_ID = '\0' + VIRTUAL_ID;

function siteRoot() {
  return fileURLToPath(new URL('..', import.meta.url));
}

async function loadConfig() {
  const config = (await import(new URL('../odusite.config.mjs', import.meta.url).href)).default;
  const blocks = { ...config.blocks };
  for (const name of Object.keys(blocks)) {
    const override = process.env[`ODUSITE_BLOCK_${name.toUpperCase()}`];
    if (override !== undefined) blocks[name] = override === '1' || override === 'true';
  }
  const theme = process.env.ODUSITE_THEME || config.theme || 'default';
  return { ...config, blocks, theme };
}

/** @returns {import('astro').AstroIntegration} */
export function odusiteBlocks() {
  return {
    name: 'odusite-blocks',
    hooks: {
      'astro:config:setup': async ({ injectRoute, updateConfig, logger }) => {
        const config = await loadConfig();
        const root = siteRoot();
        const enabled = Object.entries(config.blocks)
          .filter(([, on]) => on)
          .map(([name]) => name);

        // Inject routes of enabled blocks from their manifest.mjs.
        for (const name of enabled) {
          const manifestPath = path.join(root, 'src', 'blocks', name, 'manifest.mjs');
          if (!existsSync(manifestPath)) {
            logger.warn(`block "${name}" enabled but ${manifestPath} is missing — skipped`);
            continue;
          }
          const manifest = (await import(`${manifestPath}?t=${Date.now()}`)).default;
          for (const route of manifest.routes ?? []) {
            injectRoute({
              pattern: route.pattern,
              entrypoint: path.join(root, 'src', 'blocks', name, route.entrypoint),
              prerender: route.prerender ?? false,
            });
          }
          logger.info(`block "${name}": ${manifest.routes?.length ?? 0} routes`);
        }

        const themeDir = path.join(root, 'src', 'themes', config.theme);
        if (!existsSync(themeDir)) {
          throw new Error(`Odusite theme "${config.theme}" not found at ${themeDir}`);
        }

        updateConfig({
          vite: {
            plugins: [
              {
                name: 'odusite-virtual-config',
                resolveId(id) {
                  if (id === VIRTUAL_ID) return RESOLVED_VIRTUAL_ID;
                  // Active theme stylesheet: import 'virtual:odusite/theme.css'
                  if (id === 'virtual:odusite/theme.css') {
                    return path.join(themeDir, 'global.css');
                  }
                },
                load(id) {
                  if (id === RESOLVED_VIRTUAL_ID) {
                    const nav = (config.nav ?? []).filter(
                      (item) => !item.block || config.blocks[item.block],
                    );
                    return `export default ${JSON.stringify({
                      blocks: config.blocks,
                      theme: config.theme,
                      nav,
                    })};`;
                  }
                },
              },
              {
                // "@theme/X" resolves to the active theme's override when it
                // exists, otherwise to the core themeable component.
                name: 'odusite-theme-alias',
                resolveId(id) {
                  if (!id.startsWith('@theme/')) return null;
                  const rest = id.slice('@theme/'.length);
                  const candidates = [
                    path.join(themeDir, 'components', rest),
                    path.join(root, 'src', 'components', 'themeable', rest),
                  ];
                  for (const candidate of candidates) {
                    if (existsSync(candidate)) return candidate;
                  }
                  throw new Error(`@theme/${rest} not found in theme "${config.theme}" nor core themeable components`);
                },
              },
            ],
          },
        });
      },
    },
  };
}
