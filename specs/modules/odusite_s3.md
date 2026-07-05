# odusite_s3

Depends: `odusite_base`. External dependency: `boto3` (declared in the manifest
`external_dependencies`; see ADR-008, ADR-012).

Offloads the Odoo `ir.attachment` filestore to S3-compatible object storage
(AWS S3 or Cloudflare R2) so that all media and documents served to the
frontend live off the Odoo host.

## Configuration

System parameters (edited in Settings → Odusite → Object Storage), all under
the `odusite.s3.*` namespace:

| Parameter | Purpose |
|---|---|
| `odusite.s3.enabled` | Master switch. When off, Odoo uses its normal filestore. |
| `odusite.s3.endpoint_url` | S3 endpoint (e.g. `https://<acct>.r2.cloudflarestorage.com`). |
| `odusite.s3.region` | Region (`auto` for R2). |
| `odusite.s3.bucket` | Bucket name. |
| `odusite.s3.access_key` / `odusite.s3.secret_key` | Credentials (secret stored write-only in the UI). |
| `odusite.s3.public_base_url` | Public CDN/R2 base URL for public objects (e.g. `https://media.example.com`). Empty ⇒ no direct public URLs, only the `/img` proxy + presigned. |
| `odusite.s3.url_expiry` | Presigned GET lifetime in seconds (default 900). |

A **Test connection** button validates credentials by writing and deleting a
probe object.

## Storage offload

Extends `ir.attachment`:
- `_storage()` returns `'odusite_s3'` when `odusite.s3.enabled` **and** the
  attachment is *offloadable* (see policy), else falls back to `super()`.
- `_file_read(fname)` / `_file_write(bin_value, checksum)` / `_file_delete(fnames)`
  implement the `odusite_s3` backend against the bucket, keyed by the same
  sha1-based `store_fname` Odoo already computes (`xx/xxxx…`). Content is stored
  once per checksum (dedup preserved). A small in-process client cache reuses
  the boto3 session.

**Offload policy** (`_odusite_s3_offloadable`): offload everything **except**
Odoo backend web assets and generated bundles — attachments where
`res_model = 'ir.ui.view'`, `name` starts with `/web/assets`, or mimetype is
`text/css` / `application/javascript` / `text/scss`. This keeps the admin UI
fast (assets read from the local filestore) while product images, blog/event
covers, PDFs and uploads go to S3. The policy is overridable.

## Presigned URLs (private documents)

- `ir.attachment._odusite_presigned_url(expiry=None)` → time-limited signed GET
  URL for the object (only for S3-stored attachments; raises otherwise).
- Registered as a shared helper so `odusite_account` / `odusite_sale` PDF
  endpoints return `{download_url}` (presigned) instead of streaming the file
  through the worker. When S3 is disabled they fall back to the existing stream.

## Public image URLs (hybrid delivery)

- `odusite.s3` extends the `odusite_base` `image_url` serializer: for a public,
  S3-offloaded attachment it can return the direct `public_base_url/<key>` of
  the **original**. Sized variants keep using the `/web/image/...` → `/img`
  proxy (Odoo resizes on the fly; source bytes come from S3; result edge-cached
  by `unique`).
- Serializer helper `public_asset(record, field)` returns
  `{original: <r2-url|null>, proxy: /web/image/...}` so the site chooses per
  context (thumbnail → proxy, full/download → original).

## Migration of existing filestore

- New attachments are written to S3 immediately once enabled.
- Existing local attachments are **not** touched automatically. A server action
  *"Migrate filestore to S3"* and an optional cron (`_odusite_s3_migrate_batch`,
  batched, idempotent) copy offloadable local attachments to S3 and flip their
  storage, logging progress. Reversible by disabling the master switch (reads
  fall back per-attachment based on where the bytes actually are).

## Endpoints

No new public endpoints. Offload and presigning are internal; the frontend sees
only richer `image`/`download_url` fields on existing endpoints.

## Testing

Tested against a MinIO sidecar (S3-compatible) provisioned in the dev
environment; unit tests cover offload policy, read/write/delete round-trip,
presigned URL generation, and the public/proxy URL split. `boto3` is installed
in the test container.
