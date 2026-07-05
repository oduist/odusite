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

Declared on the agent (ElevenLabs config) and implemented in the widget, wired to
the View Transitions router (`astro:transitions/client` `navigate`):

| Tool | Params | Effect |
|---|---|---|
| `navigate` | `path` (absolute, `/…`) | SPA-navigate to a site page. |
| `search_site` | `query` | Navigate to `/search?q=<query>`. |

The agent's system prompt lists the site sections (shop, blog, events, jobs,
forum, courses, portal, …) and is told to call `navigate` / `search_site` only
when the visitor asks to go somewhere or find something.

## Notes

- Requires an ElevenLabs agent configured with the two client tools above.
- A real microphone + WebRTC/WebSocket are needed for an actual conversation;
  headless/CI environments exercise the flow up to the connection attempt.
- No Odoo involvement — this is a pure site feature.
