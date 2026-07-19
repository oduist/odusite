# Voice assistant (ElevenLabs Conversational AI)

An optional, hands-free voice assistant embedded site-wide. It lets a visitor
talk to a conversational agent that can answer questions and **navigate the
site** for them. Off by default; enabled purely by server configuration.

## Activation

Rendered only when the server has `ELEVENLABS_AGENT_ID` set (checked in
`Base.astro` via `getEnv`). Unconfigured ⇒ the component is not emitted and ships
zero JS. The ElevenLabs **API key never reaches the browser**.

Env (server-side): `ELEVENLABS_API_KEY` (secret), `ELEVENLABS_AGENT_ID`.

## Token broker

`GET /api/voice/signed-url` (`src/pages/api/voice/signed-url.ts`, `prerender =
false`) calls ElevenLabs `GET /v1/convai/conversation/get-signed-url` with the
server API key and returns `{ signed_url }` (a short-lived `wss://` URL that
already embeds the agent). `no-store`. Returns 503 when unconfigured, 502 on
upstream failure.

## Widget

`components/VoiceAssistant.astro` — a fixed mic button + status line.
- `transition:persist`, so an in-progress call survives View Transitions
  navigations (the assistant keeps talking while pages change).
- The `@elevenlabs/client` SDK is **dynamically imported on first click**, so an
  idle visitor pays no JS for it.
- Click → fetch signed URL → `Conversation.startSession({ signedUrl, clientTools,
  onStatusChange, onModeChange, onError })`. Status reflects
  Connecting/Listening/Speaking; a denied microphone shows "Microphone needed".
  Clicking again ends the session. The live conversation is held on `window` so
  it survives both the transition and any script re-run.

## Client tools (agent → browser)

Wired to the View Transitions router (`astro:transitions/client` `navigate`):

| Tool | Params | Effect |
|---|---|---|
| `navigate` | `path` (absolute, `/…`) | SPA-navigate to a known site section. |
| `search_site` | `query` | Navigate to `/search?q=<query>`. |
| `click_on_page` | `text` | Open a specific entity **visible on the current page** by its name. |

**Single source of truth.** The tool contracts (name, description, JSON-schema
params) live in `src/voice/tools.mjs`, imported by both the widget (which
implements a handler per tool) and the provisioner (which registers them on the
agent), so the two can never drift. The widget asserts in dev that every declared
tool has a handler.

`navigate` and `search_site` are "blind" (known routes / keyword redirect).
`click_on_page` is perception-based: to open an individual product / post /
event / job / partner / forum thread, the agent first `navigate`s or
`search_site`s to a listing, then calls `click_on_page` with the item's name.
This keeps the mechanism universal across blocks without any per-entity backend.

### `click_on_page` resolution

The handler scans the current DOM and picks a link to follow:
1. **Annotated targets (primary):** elements carrying `data-voice-label="<name>"`
   inside `<main>`. Blocks mark their canonical entity links (see below).
2. **Fallback:** if none are annotated on the page, internal (`/…`) anchors
   inside `<main>` by their visible/`aria-label` text.

Matching is normalised (case/diacritics/punctuation-insensitive) and tiered:
exact → prefix → substring. Zero matches ⇒ returns a few visible labels so the
agent can offer to search; multiple ⇒ returns the candidates so the agent asks
which one; one ⇒ same-origin `navigate` to its `href` (or `.click()` if it has
none). Only internal `/…` links are ever followed — never external or
`javascript:` targets.

### `data-voice-label` convention

Any block that renders navigable entities marks the **canonical link** to each
one with `data-voice-label="<visible name>"`. The themeable `Card.astro` exposes
a `voiceLabel` prop that emits the attribute on its anchor; raw entity `<a>`
links (forum thread rows, search results) set it directly. Applied so far: shop
products, blog posts, events, jobs, partners, courses, forum threads & forums,
and search results.

## Provisioning the agent (`pnpm voice:sync`)

`scripts/voice-sync.mjs` reconciles the ElevenLabs agent from the site's own
config — the agent is derived, not hand-edited:

- **Prompt** — `src/voice/prompt.mjs` `buildAgentPrompt({blocks, nav, siteName})`
  generates the system prompt from the **enabled blocks** (same block resolution
  as the build, incl. `ODUSITE_BLOCK_*` overrides): the section list for
  `navigate`, the three tools, and the "navigate/search → click" pattern.
- **Tools** — from `tools.mjs`. The script lists existing ElevenLabs tools,
  **creates** the missing ones, updates drifted ones, and attaches their ids to
  the agent (preserving any foreign tool ids already on it).
- **Agent** — `PATCH`es `conversation_config.agent.prompt.{prompt,tool_ids}` on
  `ELEVENLABS_AGENT_ID`; with `--create` (no id yet) it creates one and prints
  the id to store. It never touches voice/LLM/persona — those stay owned by the
  ElevenLabs dashboard.
- Idempotent; `--dry-run` prints the planned diff and the prompt without writing.
  Runs by hand or as a deploy step. Needs `ELEVENLABS_API_KEY` (shell env or
  `site/.dev.vars`).

## Notes

- A real microphone + WebRTC/WebSocket are needed for an actual conversation;
  headless/CI environments exercise the flow up to the connection attempt.
- No Odoo involvement — this is a pure site feature.
