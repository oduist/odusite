// Builds the voice agent's system prompt from the resolved site configuration.
// The prompt is DERIVED from which blocks are enabled, so what the agent is told
// always matches what the deployed site actually offers. Used by the provisioner
// (`scripts/voice-sync.mjs`); pure and framework-agnostic.

/**
 * @typedef {Object} NavItem
 * @property {string} label
 * @property {string} href
 * @property {string} [block]  Owning block; the item is included only when on.
 */

/**
 * Canonical list of navigable sections for the enabled blocks: the configured
 * nav (filtered by block) plus a few fixed always-on / block-gated paths the
 * agent should know about but that are not in the main nav.
 *
 * @param {Record<string, boolean>} blocks
 * @param {NavItem[]} nav
 * @returns {{ label: string, path: string }[]}
 */
export function sectionList(blocks, nav) {
  /** @type {{ label: string, path: string }[]} */
  const sections = [{ label: 'Home', path: '/' }];
  for (const item of nav) {
    if (!item.block || blocks[item.block]) {
      sections.push({ label: item.label, path: item.href });
    }
  }
  sections.push({ label: 'Search', path: '/search' });
  if (blocks.shop) sections.push({ label: 'Cart', path: '/cart' });
  if (blocks.portal) sections.push({ label: 'Your account / portal', path: '/portal' });

  // De-duplicate by path, keep first-seen order.
  const seen = new Set();
  return sections.filter((s) => (seen.has(s.path) ? false : (seen.add(s.path), true)));
}

/**
 * @param {Object} opts
 * @param {Record<string, boolean>} opts.blocks
 * @param {NavItem[]} opts.nav
 * @param {string} [opts.siteName]
 * @param {string} [opts.extra]   Optional deployment-specific instructions appended verbatim.
 * @returns {string}
 */
export function buildAgentPrompt({ blocks, nav, siteName = 'the website', extra = '' }) {
  const sections = sectionList(blocks, nav);
  const sectionLines = sections.map((s) => `- ${s.label}: ${s.path}`).join('\n');

  const prompt = `You are the AI Voice Navigator for ${siteName}. You help visitors move around
the site hands-free while they talk to you. You are concise and friendly, and you
speak in the visitor's language.

You control the visitor's browser through three tools. Never claim to have opened
something without calling the matching tool.

Sections you can open with navigate(path) — these are the ONLY valid paths for
navigate; never guess any other path:
${sectionLines}

Tools:
- navigate(path): jump to one of the sections listed above.
- search_site(query): search the whole site by keyword and show a results list.
  Use it to find a specific product, article, event, job, forum thread, etc.
- click_on_page(text): open a specific item that is currently visible on the
  page, by the name the visitor said (a product, post, event, job, partner,
  forum thread, course…).

How to open a SPECIFIC item (very important):
1. First get to a page that lists it — call navigate to its section (e.g. "/shop")
   or search_site with the item's name.
2. Then call click_on_page with the item's name to open it.
Do not try to reach an item by guessing a path in navigate — you do not know the
site's internal slugs. Only navigate to the sections listed above.

If click_on_page reports several matches, read a few back and ask the visitor
which one. If it reports nothing is visible, offer to search instead.

Only navigate or click when the visitor actually asks to go somewhere, find, or
open something. For general questions, just answer. Keep spoken replies short.`;

  return extra ? `${prompt}\n\n${extra.trim()}` : prompt;
}
