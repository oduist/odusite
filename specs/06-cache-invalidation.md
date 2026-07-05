# Cache Invalidation (Odoo → Site webhooks)

Implemented in `odusite_base`.

## Model `odusite.webhook.event` (queue)

| Field | Type | Purpose |
|---|---|---|
| model | char | e.g. `blog.post` |
| res_id | integer | record id |
| event | selection: created / updated / deleted / published / unpublished | change type |
| tags | char | cache tags, comma-separated (e.g. `blog,blog:42`) |
| state | selection: pending / sent / failed | delivery state |
| attempts | integer | retry counter |
| payload | text (json) | snapshot sent to the site |

## Mechanics

1. Odusite modules register their models in a registry
   (`odusite.exposed.models`): model → list of watched fields + tag builder.
   `odusite_base` hooks `write/create/unlink` of registered models
   (via an abstract mixin `odusite.watched.mixin` inherited into each model)
   and enqueues events. Only published-relevant changes enqueue (watched
   fields, publish flag transitions).
2. A cron (every minute, batched) POSTs pending events to
   `<odusite.site_url>/api/revalidate` with headers
   `X-Odusite-Signature: hex(hmac_sha256(ODUSITE_REVALIDATE_SECRET, body))`
   and body `{events: [{model, id, event, tags, at}]}`.
   Retry with backoff (max 5 attempts → `failed`).
3. The Worker endpoint `/api/revalidate` verifies the HMAC and purges the edge
   cache by tags (Cache API keys are tag-indexed via KV) — or, in the simple
   deployment, purges the affected URL families.
4. Manual controls: admin can re-send failed events; "Purge all" server action
   sends a `{events:[{tags:["all"]}]}` payload.

## Cache tags convention

`<block>` (listing pages) and `<block>:<id>` (detail page), e.g.
`shop`, `shop:123`, `blog`, `blog:42`, `site` (menus/settings).
The site assigns the same tags when storing responses in the edge cache.
