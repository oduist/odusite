# Voice assistant (ElevenLabs) — setup

The site can embed an optional voice assistant powered by ElevenLabs
Conversational AI. It is **off unless configured**.

## Prerequisites

1. An ElevenLabs account and an API key.
2. A **Conversational AI agent** created in the ElevenLabs dashboard, configured
   with two **client tools**:
   - `navigate` — one string parameter `path` (an absolute site path).
   - `search_site` — one string parameter `query`.
   Give the agent a system prompt describing your site's sections and instruct it
   to call these tools to move the visitor around / search.

## Configuration

Set two server-side variables (Cloudflare Worker secrets in production,
`site/.dev.vars` in development — never commit them):

| Variable | Purpose |
|---|---|
| `ELEVENLABS_API_KEY` | Secret API key. Used only server-side to mint signed URLs. |
| `ELEVENLABS_AGENT_ID` | The agent to connect visitors to. |

In production add them with `wrangler secret put ELEVENLABS_API_KEY` (and the
agent id). When both are present the mic widget appears; when absent the site
ships no voice code at all.

## How it works

The browser never sees the API key. It requests a short-lived signed WebSocket
URL from `/api/voice/signed-url` (which calls ElevenLabs with the key), then
connects directly. The agent drives navigation through the two client tools.

## Notes & privacy

- Conversation minutes are billed by ElevenLabs against your account/plan.
- The visitor grants microphone permission per browser; audio streams only
  during an active conversation.
- To rotate the key, update the secret and redeploy; existing signed URLs expire
  on their own (short TTL).
