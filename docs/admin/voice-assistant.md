# Voice assistant (ElevenLabs) — setup

The site can embed an optional voice assistant powered by ElevenLabs
Conversational AI. It is **off unless configured**.

## Prerequisites

1. An ElevenLabs account and an API key.
2. A **Conversational AI agent** in the ElevenLabs dashboard. You only pick the
   voice, language, and LLM there — **you do not configure the client tools or
   the system prompt by hand**. Those are provisioned from this repo with
   `pnpm voice:sync` (see *Provisioning the agent* below), which keeps them in
   step with which blocks your site ships.

The agent drives the browser through three client tools:
- `navigate(path)` — go to a known site section.
- `search_site(query)` — run a site search.
- `click_on_page(text)` — open a specific item visible on the current page
  (a product, article, event, job, forum thread, …) by its name.

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

## Provisioning the agent (`pnpm voice:sync`)

Instead of editing the agent in the dashboard, generate its prompt and tools
from the site config:

```bash
cd site
# preview the changes without writing anything
ELEVENLABS_API_KEY=… ELEVENLABS_AGENT_ID=… pnpm voice:sync --dry-run
# apply
ELEVENLABS_API_KEY=… ELEVENLABS_AGENT_ID=… pnpm voice:sync
```

What it does, idempotently:
- Builds the **system prompt** from your enabled blocks (respects
  `ODUSITE_BLOCK_*`), listing the sections the agent may open and teaching it the
  *search/navigate → click* flow for individual items.
- **Creates any missing client tools** (`navigate`, `search_site`,
  `click_on_page`) on your ElevenLabs workspace and updates drifted ones.
- Attaches those tools to the agent and sets its prompt. It never changes the
  agent's voice, LLM, or persona — those stay owned by the dashboard.

Flags / env:
- `--dry-run` — print the planned diff and the prompt, write nothing.
- `--create` — create a new agent (use when `ELEVENLABS_AGENT_ID` is not set
  yet); it prints the new id to store as a secret.
- `--site-name="My Store"` or `ODUSITE_SITE_NAME` — name used in the prompt.
- Reads `ELEVENLABS_API_KEY` / `ELEVENLABS_AGENT_ID` from the shell or
  `site/.dev.vars`.

Re-run `voice:sync` whenever you enable/disable blocks or after updating the tool
definitions.

### In CI

The `Deploy site` workflow (`.github/workflows/deploy-site.yml`) runs
`pnpm voice:sync --skip-if-unconfigured` after each deploy, so the agent is
re-provisioned on every push to `main`. Set the repo **secrets**
`ELEVENLABS_API_KEY` and `ELEVENLABS_AGENT_ID` (and optionally the repo
**variable** `ODUSITE_SITE_NAME`) to enable it. When those secrets are absent the
step is a clean no-op, so deployments without the voice assistant are unaffected.
`--skip-if-unconfigured` turns "not configured" into a successful skip instead of
an error.

## How it works

The browser never sees the API key. It requests a short-lived signed WebSocket
URL from `/api/voice/signed-url` (which calls ElevenLabs with the key), then
connects directly. The agent drives navigation through the three client tools;
`click_on_page` opens individual items by matching the visible name against the
links on the current page (blocks tag their entity links with
`data-voice-label`), so no product/article URLs are hardcoded anywhere.

## Notes & privacy

- Conversation minutes are billed by ElevenLabs against your account/plan.
- The visitor grants microphone permission per browser; audio streams only
  during an active conversation.
- To rotate the key, update the secret and redeploy; existing signed URLs expire
  on their own (short TTL).
