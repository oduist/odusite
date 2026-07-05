# odusite_s3

Depends: `odusite_base`. External dependency: `boto3` (declared in the manifest
`external_dependencies`; see ADR-008, ADR-012).

Offloads the Odoo `ir.attachment` filestore to S3-compatible object storage
(AWS S3 or Cloudflare R2) so that all media and documents served to the
frontend live off the Odoo host. The design adopts the production techniques of
an internal reference module (`s3_attachment`): an `s3://` storage marker,
deferred reference-counted GC, and a throttled background migration.

## Configuration

Connection settings are resolved in this precedence (secrets can stay out of the
DB for hardening, while the Settings UI remains available for quick testing):

1. `odoo.conf` `[options]` → `odusite_s3_<name>`
2. environment variable → `ODUSITE_S3_<NAME>`
3. database system param → `odusite.s3.<name>` (Settings → Website → Odusite)

Keys (`<name>`): `endpoint_url`, `public_endpoint_url`, `public_base_url`,
`region`, `bucket`, `access_key`, `secret_key`. DB-only policy params:
`enabled`, `url_expiry`, `direct_download`, `keep_assets_local`,
`keep_images_below_kb`, `keep_local_mimetypes`, plus migration params
(`migrate_active`, `migrate_batch_size`, `migrate_workers`,
`migrate_window_start`/`_end`/`_tz`). `public_endpoint_url` is a browser-facing
endpoint for presigned URLs when the server talks to S3 over a private address.

Settings (Website → Odusite → *Object Storage*) shows a live **connection
status**, migration **progress counters** (on S3 / local pending / running) and
**Test connection** / **Migrate: Start / Stop / Refresh** buttons.

## Storage offload (`s3://` marker)

Extends `ir.attachment`. An S3-backed file is recorded as an
`s3://<sha[:2]>/<sha>` prefix in `store_fname`, so storage is **per-record and
self-describing** — reads route on the prefix and un-migrated local files keep
working. `_storage()` is **not** overridden.

- `_get_datas_related_values(data, mimetype)` — the single routing point (has
  both mimetype and size): when the policy says "offload", it uploads via the
  flagged `_file_write` and records the `s3://` `store_fname` (Odoo 19 discards
  `_file_write`'s return during `create`, so the value is set here).
- `_file_read(fname, size)` / `_file_write(bin_value, checksum)` — GET/PUT the
  object keyed by the sha1 `store_fname` (content-addressed ⇒ dedup, HEAD before
  PUT). `_file_read` falls back to `super()` for local (non-`s3://`) files.
- `_file_delete(fname)` — for `s3://` files, queues the key in `odusite.s3.gc`
  (see GC) instead of deleting inline.
- `_to_http_stream()` — S3-backed binaries have no local file, so they stream as
  `data` (bytes read from S3); required because `/web/image` and `/web/content`
  serve through this in Odoo 19.

**Offload policy** (`_odusite_s3_should_offload(mimetype, size)`, overridable):
offload everything except web assets (`keep_assets_local`, default true → CSS/JS
mimetypes stay local for a fast admin UI), small images
(`keep_images_below_kb`, default 50 — avatars/thumbnails), and any extra
`keep_local_mimetypes` prefixes.

## Garbage collection (deferred, dedup-aware)

Object stores are not transactional with PostgreSQL, so deletion is decoupled:
- `odusite.s3.gc` — a queue model (`store_fname`, unique). `_file_delete` inserts
  into it in a **separate cursor** so the intent survives a rollback (mirrors
  Odoo's own filestore checklist).
- `_gc_odusite_s3_store()` (`@api.autovacuum`) → `_gc_odusite_s3_collect()`
  deletes an object only when **no** `ir.attachment` still references its
  `store_fname` (deduplication guard). Local asset bundles are still reclaimed by
  the stock filestore GC.

## Direct download & presigned URLs

- `ir.attachment._odusite_presigned_url(expiry=None)` → time-limited signed GET
  URL (raises `UserError` for non-S3 attachments so callers can fall back to
  streaming). `odusite_account` / `odusite_sale` PDF endpoints use it when S3 is
  on, else stream.
- **`ir.http` redirect** (`controllers/binary.py`): when `direct_download` is on,
  `/web/content` and `/web/image` serve an S3-backed **original** as a `302` to a
  short-lived presigned URL — after the exact same access check Odoo does — so
  the bytes leave the object store directly. Resize/crop requests fall through to
  a normal read-from-S3 (Odoo 19 removed the 15.0 `_get_content_common` /
  `_content_image` hooks; the redirect is injected at the actual 19.0 handler,
  not at `ir.binary`, so internal byte readers are unaffected).

## Public image URLs (hybrid delivery)

`odusite_s3` overrides the `odusite_base` hook `_odusite_public_asset_url(record,
field)`: for a public, S3-offloaded original it returns
`public_base_url/<object-key>` (or `public_endpoint_url/<bucket>/<object-key>`),
else `None`. The serializer `public_asset(record, field)` returns
`{original: <url|null>, proxy: /web/image/...}` so the site picks per context
(thumbnail → resized proxy, full/download → direct original).

## Migration of existing filestore

New attachments offload immediately; existing local ones are migrated by a
throttled background job (cron `_cron_odusite_s3_migrate`, inactive by default,
driven by the Start/Stop buttons):

- A `ThreadPoolExecutor` does the network-bound work (read local file + PUT);
  **no DB cursor in the worker threads**, so worker count is independent of
  `db_maxconn`. All DB work (metadata read, `store_fname` swap, commit) stays
  single-threaded in the orchestrator.
- Keyset pagination; an optional **time window** (tz-aware, overnight-capable);
  Start/Stop via `migrate_active` (read with raw SQL to bypass the ORM cache);
  concurrent-update rows deferred and retried; an unhealthy-source guard (a short
  read skips rather than storing empty bytes).
- The `store_fname` swap is a **direct SQL UPDATE** bypassing the ORM `write`
  chain, so relocation does not fire sibling modules' business-logic write hooks
  — a pure storage move that keeps checksum/size/dedup intact.
- Reversible: disabling the master switch makes reads fall back per-attachment
  based on where the bytes actually are.

## Endpoints

No new public API endpoints. Offload, GC, presigning and the direct-download
redirect are internal; the frontend sees only richer `image` / `download_url`
fields on existing endpoints.

## Testing

Tested against an S3-compatible mock sidecar (adobe/s3mock, path-style) reachable
from the Odoo container; `boto3` is installed in the test container. Tests cover
the offload policy, the `s3://` round-trip (write → object present → read →
local fallback), dedup, deferred GC (unreferenced removed, referenced kept),
presigned URLs, and the public/proxy hybrid split. The storage suite skips
cleanly when the mock is unreachable.
