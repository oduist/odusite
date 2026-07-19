#!/usr/bin/env node
// Provision the ElevenLabs Conversational AI agent from the site's own config.
//
// The site is the source of truth: this reconciles the agent's system prompt
// (derived from the enabled blocks) and its client tools (from src/voice/
// tools.mjs) onto ElevenLabs — creating any tool that does not exist yet and
// attaching all of them to the agent. Idempotent; run it on deploy or by hand.
//
//   node scripts/voice-sync.mjs [--dry-run] [--create] [--site-name="My Site"]
//
// Env (from the shell or site/.dev.vars):
//   ELEVENLABS_API_KEY   required — used only here, server-side.
//   ELEVENLABS_AGENT_ID  the agent to manage. Omit + pass --create to create one.
//   ODUSITE_SITE_NAME    optional display name used in the prompt.
//   ODUSITE_BLOCK_*      same build-time block overrides as the site build.
//
// The dashboard still owns the agent's voice, LLM and persona knobs; this only
// manages the prompt text and the tool attachments.

import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import { VOICE_TOOLS } from '../src/voice/tools.mjs';
import { buildAgentPrompt } from '../src/voice/prompt.mjs';

const SITE_ROOT = fileURLToPath(new URL('..', import.meta.url));
const API_BASE = 'https://api.elevenlabs.io';

// --- CLI + env ------------------------------------------------------------

const args = process.argv.slice(2);
const flag = (name) => args.includes(`--${name}`);
const opt = (name) => {
  const hit = args.find((a) => a.startsWith(`--${name}=`));
  return hit ? hit.slice(name.length + 3) : undefined;
};

const DRY_RUN = flag('dry-run');
const CREATE = flag('create');
// For CI: exit 0 (no-op) instead of failing when ElevenLabs is not configured,
// so deployments without the voice assistant don't break the pipeline.
const SKIP_IF_UNCONFIGURED = flag('skip-if-unconfigured');

/** Load site/.dev.vars (KEY=VALUE) as a fallback for local runs. */
function loadDevVars() {
  const file = path.join(SITE_ROOT, '.dev.vars');
  if (!existsSync(file)) return {};
  /** @type {Record<string,string>} */
  const out = {};
  for (const raw of readFileSync(file, 'utf8').split('\n')) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    const eq = line.indexOf('=');
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    let val = line.slice(eq + 1).trim();
    if (
      (val.startsWith('"') && val.endsWith('"')) ||
      (val.startsWith("'") && val.endsWith("'"))
    ) {
      val = val.slice(1, -1);
    }
    out[key] = val;
  }
  return out;
}

const devVars = loadDevVars();
// Treat empty strings (e.g. an unset GitHub secret interpolated as "") as unset.
const env = (key) => {
  const v = process.env[key] ?? devVars[key];
  return v === '' ? undefined : v;
};

const API_KEY = env('ELEVENLABS_API_KEY');
let AGENT_ID = env('ELEVENLABS_AGENT_ID');
const SITE_NAME = opt('site-name') ?? env('ODUSITE_SITE_NAME') ?? 'the website';

function die(msg) {
  console.error(`✖ ${msg}`);
  process.exit(1);
}

const unconfigured = !API_KEY || (!AGENT_ID && !CREATE);
if (unconfigured && SKIP_IF_UNCONFIGURED) {
  console.log('Voice assistant not configured (no ElevenLabs key/agent) — skipping sync.');
  process.exit(0);
}
if (!API_KEY) die('ELEVENLABS_API_KEY is not set (shell env or site/.dev.vars).');
if (!AGENT_ID && !CREATE) {
  die('ELEVENLABS_AGENT_ID is not set. Pass --create to create a new agent, or set the id.');
}

// --- Resolved site config (mirrors integrations/blocks.mjs) ---------------

async function loadResolvedConfig() {
  const mod = await import(new URL('../odusite.config.mjs', import.meta.url).href);
  const config = mod.default;
  const blocks = { ...config.blocks };
  for (const name of Object.keys(blocks)) {
    const override = process.env[`ODUSITE_BLOCK_${name.toUpperCase()}`];
    if (override !== undefined) blocks[name] = override === '1' || override === 'true';
  }
  return { blocks, nav: config.nav ?? [] };
}

// --- ElevenLabs REST ------------------------------------------------------

async function api(method, endpoint, body) {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    method,
    headers: {
      'xi-api-key': API_KEY,
      ...(body ? { 'Content-Type': 'application/json' } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`${method} ${endpoint} → ${res.status} ${res.statusText}: ${text}`);
  }
  return res.status === 204 ? null : res.json();
}

async function listTools() {
  /** @type {{id: string, tool_config: any}[]} */
  const tools = [];
  let cursor = '';
  do {
    const qs = cursor ? `?cursor=${encodeURIComponent(cursor)}` : '';
    const page = await api('GET', `/v1/convai/tools${qs}`);
    tools.push(...(page.tools ?? []));
    cursor = page.has_more ? page.next_cursor : '';
  } while (cursor);
  return tools;
}

const createTool = (cfg) => api('POST', '/v1/convai/tools', { tool_config: cfg });
const updateTool = (id, cfg) => api('PATCH', `/v1/convai/tools/${id}`, { tool_config: cfg });
const getAgent = (id) => api('GET', `/v1/convai/agents/${id}`);
const patchAgent = (id, body) => api('PATCH', `/v1/convai/agents/${id}`, body);
const createAgent = (body) => api('POST', '/v1/convai/agents/create', body);

// --- Helpers --------------------------------------------------------------

/** Our spec → ElevenLabs client-tool config (only the fields we manage). */
const toToolConfig = (spec) => ({
  type: 'client',
  name: spec.name,
  description: spec.description,
  parameters: spec.parameters,
  expects_response: spec.expects_response,
  response_timeout_secs: spec.response_timeout_secs,
});

/** Deterministic JSON for comparing configs regardless of key order. */
function stable(value) {
  if (Array.isArray(value)) return `[${value.map(stable).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value)
      .sort()
      .map((k) => `${JSON.stringify(k)}:${stable(value[k])}`)
      .join(',')}}`;
  }
  return JSON.stringify(value);
}

/** True when the existing tool_config already matches our managed fields. */
function toolMatches(existing, desired) {
  const pick = (c) => ({
    type: c?.type,
    name: c?.name,
    description: c?.description,
    parameters: c?.parameters,
    expects_response: c?.expects_response,
    response_timeout_secs: c?.response_timeout_secs,
  });
  return stable(pick(existing)) === stable(pick(desired));
}

// --- Reconcile ------------------------------------------------------------

async function run() {
  const { blocks, nav } = await loadResolvedConfig();
  const prompt = buildAgentPrompt({ blocks, nav, siteName: SITE_NAME });

  console.log(`Voice agent sync${DRY_RUN ? ' (dry run — no writes)' : ''}`);
  console.log(`  site name : ${SITE_NAME}`);
  console.log(`  blocks on : ${Object.keys(blocks).filter((b) => blocks[b]).join(', ') || '(none)'}`);
  console.log(`  tools     : ${VOICE_TOOLS.map((t) => t.name).join(', ')}`);

  // 1) Reconcile tools: create missing, update drifted, reuse the rest.
  const existingTools = await listTools();
  const validToolIds = new Set(existingTools.map((t) => t.id));
  const managedIds = [];

  for (const spec of VOICE_TOOLS) {
    const desired = toToolConfig(spec);
    const found = existingTools.find(
      (t) => t.tool_config?.type === 'client' && t.tool_config?.name === spec.name,
    );
    if (!found) {
      if (DRY_RUN) {
        console.log(`  + create tool "${spec.name}"`);
        managedIds.push(`(new:${spec.name})`);
        continue;
      }
      const created = await createTool(desired);
      console.log(`  + created tool "${spec.name}" → ${created.id}`);
      managedIds.push(created.id);
      validToolIds.add(created.id);
    } else if (!toolMatches(found.tool_config, desired)) {
      if (DRY_RUN) console.log(`  ~ update tool "${spec.name}" (${found.id})`);
      else {
        await updateTool(found.id, desired);
        console.log(`  ~ updated tool "${spec.name}" → ${found.id}`);
      }
      managedIds.push(found.id);
    } else {
      console.log(`  = tool "${spec.name}" up to date (${found.id})`);
      managedIds.push(found.id);
    }
  }

  // 2) Reconcile the agent (create or patch prompt + tool attachments).
  if (!AGENT_ID) {
    const body = {
      name: `${SITE_NAME} — AI Voice Navigator`,
      conversation_config: {
        agent: { prompt: { prompt, tool_ids: managedIds }, language: 'en' },
      },
    };
    if (DRY_RUN) {
      console.log('  + create agent (dry run) — pass without --dry-run to apply');
      printPrompt(prompt);
      return;
    }
    const created = await createAgent(body);
    console.log(`\n✔ Created agent ${created.agent_id}`);
    console.log(`  Store it: wrangler secret put ELEVENLABS_AGENT_ID  (value: ${created.agent_id})`);
    return;
  }

  const agent = await getAgent(AGENT_ID);
  const current = agent?.conversation_config?.agent?.prompt ?? {};
  const currentToolIds = Array.isArray(current.tool_ids) ? current.tool_ids : [];
  // Keep foreign tools already on the agent; drop ids that no longer exist.
  const desiredToolIds = [
    ...new Set([...currentToolIds.filter((id) => validToolIds.has(id)), ...managedIds]),
  ];

  const promptChanged = current.prompt !== prompt;
  const toolsChanged = stable([...currentToolIds].sort()) !== stable([...desiredToolIds].sort());

  if (!promptChanged && !toolsChanged) {
    console.log(`\n✔ Agent ${AGENT_ID} already up to date.`);
    return;
  }

  console.log(`\nAgent ${AGENT_ID} changes:`);
  if (promptChanged) console.log('  ~ system prompt');
  if (toolsChanged) console.log(`  ~ tool_ids → [${desiredToolIds.join(', ')}]`);

  if (DRY_RUN) {
    printPrompt(prompt);
    console.log('\n(dry run — nothing written)');
    return;
  }

  await patchAgent(AGENT_ID, {
    conversation_config: { agent: { prompt: { prompt, tool_ids: desiredToolIds } } },
  });
  console.log(`✔ Agent ${AGENT_ID} updated.`);
}

function printPrompt(prompt) {
  console.log('\n----- system prompt -----');
  console.log(prompt);
  console.log('-------------------------');
}

run().catch((err) => die(err.message));
