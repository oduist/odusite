// Single source of truth for the voice assistant's client tools.
//
// This module is imported by BOTH consumers so their view of the tools can
// never drift:
//   - the widget (`components/VoiceAssistant.astro`) implements a handler for
//     every tool listed here and passes them to the ElevenLabs SDK;
//   - the provisioner (`scripts/voice-sync.mjs`) registers these exact specs on
//     the ElevenLabs agent (creating tools that do not exist yet).
//
// Keep this framework-agnostic and serialisable: plain data + JSON-schema
// parameter definitions, no DOM/Node APIs. The `parameters` object is passed
// verbatim to ElevenLabs as the tool's `parameters` (JSON-schema object).

/**
 * @typedef {Object} VoiceToolSpec
 * @property {string} name          Tool name; must match the handler key in the widget.
 * @property {string} description   Told to the agent's LLM — when/how to call it.
 * @property {{ type: 'object', properties: Record<string, unknown>, required?: string[] }} parameters
 * @property {boolean} expects_response  The agent waits for the handler's return value.
 * @property {number} response_timeout_secs
 */

/** @type {VoiceToolSpec[]} */
export const VOICE_TOOLS = [
  {
    name: 'navigate',
    description:
      'Move the visitor to a known top-level section of the site. Use ONLY for the ' +
      'section paths listed in your instructions (e.g. "/shop", "/blog"). Never invent ' +
      'a path to a specific item — use search_site or click_on_page for individual ' +
      'products, articles, events, etc.',
    parameters: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description:
            'Absolute site path beginning with "/". Must be one of the sections listed ' +
            'in your instructions.',
        },
      },
      required: ['path'],
    },
    expects_response: true,
    response_timeout_secs: 5,
  },
  {
    name: 'search_site',
    description:
      'Run a site-wide search and land the visitor on the results page. Use this to ' +
      'find something by keyword (a product, article, event, job, forum thread…) when ' +
      'you do not already have it visible on the current page. After the results appear ' +
      'you can open a specific one with click_on_page.',
    parameters: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Free-text search query, e.g. a product or article name.',
        },
      },
      required: ['query'],
    },
    expects_response: true,
    response_timeout_secs: 5,
  },
  {
    name: 'click_on_page',
    description:
      'Open a specific item that is CURRENTLY VISIBLE on the page, by its visible ' +
      'name — a product, blog post, event, job, partner, forum thread, course, etc. ' +
      'If the item is not on the current page, first call navigate to its section or ' +
      'search_site to bring up a listing, then call click_on_page. If several items ' +
      'match, the tool returns the candidates so you can ask which one.',
    parameters: {
      type: 'object',
      properties: {
        text: {
          type: 'string',
          description:
            'The visible name/label of the item to open on the current page, e.g. the ' +
            'product name or article title as the visitor said it.',
        },
      },
      required: ['text'],
    },
    expects_response: true,
    response_timeout_secs: 5,
  },
];

/** Tool names, handy for drift assertions in the widget. */
export const VOICE_TOOL_NAMES = VOICE_TOOLS.map((t) => t.name);
