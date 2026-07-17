# Deployment topologies (connecting the Worker to Odoo)

The browser never talks to Odoo. Only the site's Cloudflare Worker calls Odoo's
REST API (`/odusite/v1/...`) and the image endpoint (`/web/image/...`),
server-to-server, over `ODOO_URL`. Every `/odusite/*` request carries
`X-Odusite-Token` and is rejected with 401 without it (constant-time compared;
see [ADR-002](https://github.com/oduist/odusite/blob/main/specs/decisions.md)).

Two topologies are supported. They differ only in **how the Worker reaches
Odoo** and how Odoo is exposed to the network:

- **A — Odoo private, via Cloudflare Tunnel** (recommended): Odoo has no public
  IP and no open inbound ports; it is reachable only through a `cloudflared`
  tunnel. Best for self-hosted / on-prem / private-VPS Odoo.
- **B — Public Odoo origin**: Odoo runs on a normal public HTTPS URL
  (managed Odoo, Odoo.sh, a cloud VPS) and the Worker calls it directly. Simpler
  to set up; hardening is your responsibility.

In both, `ODOO_URL` is the only thing the Worker knows about Odoo — it never
learns Odoo's IP.

---

## Topology A — Odoo private, via Cloudflare Tunnel (recommended)

```
Browser ─HTTPS─▶ Cloudflare Worker (Astro SSR)
                    │  fetch(ODOO_URL + '/odusite/v1/...')
                    │  X-Odusite-Token  (+ Bearer JWT, + CF-Access-* if used)
                    ▼
              Cloudflare edge ── routes the hostname to the tunnel
                    │  down the already-open outbound connection
                    ▼
              cloudflared  (same private network as Odoo)
                    │  http://127.0.0.1:8069
                    ▼
              Odoo 19  (no public ports)  ⇄  PostgreSQL
```

### How addressing works

- `cloudflared` runs next to Odoo and opens an **outbound** connection to
  Cloudflare's edge (QUIC, port 7844). Nothing listens for inbound traffic on
  the Odoo host — the firewall stays closed; only outbound 443/7844 is allowed.
- Odoo is addressed by a **hostname**, never an IP. The tunnel `ingress` maps a
  hostname to the local Odoo service. Cloudflare creates a DNS `CNAME` from that
  hostname to `<tunnel-id>.cfargotunnel.com` (proxied), so public DNS resolves
  to Cloudflare IPs, not to Odoo.
- The Worker just does `fetch('https://odoo-api.example.com/odusite/v1/...')`.
  Cloudflare recognises the hostname, sends the request down the existing tunnel
  connection, and `cloudflared` forwards it to `http://127.0.0.1:8069`. The
  Worker→edge hop stays inside Cloudflare's network.

### Setup

1. Install `cloudflared` on the Odoo host (or a host in the same private
   network) and create a named tunnel:

   ```bash
   cloudflared tunnel login
   cloudflared tunnel create odusite-odoo
   ```

2. Route a hostname to the tunnel and point its `ingress` at Odoo:

   ```yaml
   # /etc/cloudflared/config.yml
   tunnel: odusite-odoo
   credentials-file: /etc/cloudflared/<tunnel-id>.json
   ingress:
     - hostname: odoo-api.example.com
       service: http://127.0.0.1:8069
     # Optionally split the admin backend onto its own hostname/policy, or omit
     # it entirely so /web/* is never reachable from the tunnel.
     - service: http_status:404
   ```

   ```bash
   cloudflared tunnel route dns odusite-odoo odoo-api.example.com
   cloudflared tunnel run odusite-odoo      # or install it as a service
   ```

3. Point the site at that hostname — set `ODOO_URL=https://odoo-api.example.com`
   in `site/wrangler.jsonc` (see [site-deploy.md](site-deploy.md)).

4. Configure Odoo to trust the proxy (requests arrive proxied):
   run with `--proxy-mode` and bind to localhost only
   (`--http-interface=127.0.0.1`).

### Hardening with Cloudflare Access (recommended)

The tunnel already removes Odoo's public origin, and `X-Odusite-Token` rejects
any unauthenticated call. For defense in depth, put the hostname behind
**Cloudflare Access** with a **service-token** policy so unauthorized requests
are dropped at the edge, before they ever reach Odoo:

1. Zero Trust → Access → create a **service token**; note the Client ID and
   Client Secret.
2. Add an Access **application** for `odoo-api.example.com` with a policy that
   allows that service token (and nothing else).
3. Give the token to the Worker so it is sent on every Odoo request:

   ```bash
   cd site
   npx wrangler secret put CF_ACCESS_CLIENT_ID
   npx wrangler secret put CF_ACCESS_CLIENT_SECRET
   ```

   When both are set, the Worker adds `CF-Access-Client-Id` /
   `CF-Access-Client-Secret` to every API and `/img` request. When unset, the
   headers are simply omitted (no-op), which is the default for topology B.

Now the effective auth is: **Cloudflare Access at the edge** →
**`X-Odusite-Token` at Odoo** → **record rules / JWT** for portal data.

---

## Topology B — Public Odoo origin

Use this when Odoo already runs on a reachable HTTPS URL (managed hosting,
Odoo.sh, a cloud VPS behind Nginx/Caddy) and you do not want to run
`cloudflared`.

```
Browser ─HTTPS─▶ Cloudflare Worker ─HTTPS─▶ https://odoo.example.com (public)
                     X-Odusite-Token                    │
                     (+ Bearer JWT, + CF-Access-* )      ▼
                                                    Odoo 19 ⇄ PostgreSQL
```

### Setup

1. Deploy Odoo behind a TLS-terminating reverse proxy and run it with
   `--proxy-mode`. Only `/odusite/*` and `/web/image/*` need to be reachable by
   the Worker; keep `/web/*` (the admin backend) restricted to a VPN/allowlist.
2. Set `ODOO_URL=https://odoo.example.com` in `site/wrangler.jsonc`.

### Example: Odoo hosted on Oduflow

The reference backend runs as a persistent [Oduflow](https://oduist.com)
environment named `odusite` (repo `oduist/odusite`, branch `main`,
`odoo:19.0`), reachable at a public HTTPS origin such as
`https://odusite.team.dev.oduist.com` — i.e. plain topology B, no Cloudflare
Access, so `CF_ACCESS_*` stay unset. Notes specific to this host:

- Set `ODOO_URL` to that origin in `site/wrangler.jsonc`; set the Odoo
  `web.base.url` / `odusite.site_url` back to the Worker URL so links and the
  revalidate webhook resolve correctly.
- Addon updates land by pushing to `main` and running Oduflow `pull_and_apply`
  (install/upgrade as needed).
- Mark the environment **protected** so Oduflow's idle auto-stop (48 h) /
  auto-delete does not reap it — serving HTTP traffic does not reset that timer;
  only Oduflow tool calls do.
- `odusite_s3` needs `boto3` in the container (`pip install boto3`); reinstall it
  if the container is ever recreated.

> **Same-zone caveat (important).** Put the site Worker's custom domain and the
> Odoo origin (`ODOO_URL`) on **different Cloudflare zones**. A Worker served
> from a custom domain on zone *X* cannot reliably `fetch()` an origin hostname
> that is also on zone *X* — the server-to-server request loops back into the
> zone and pages that read Odoo return 404/empty. The reference demo runs the
> Odoo backend on `odusite.team.dev.oduist.com` (zone `oduist.com`) and therefore
> serves the site from `odusite.oduflow.dev` (zone `oduflow.dev`), not from a
> second `oduist.com` hostname.

### Hardening

`X-Odusite-Token` is mandatory and is the baseline protection, but the origin is
now publicly reachable, so add at least one edge control. Options, in rough
order of strength:

- **Proxy Odoo's domain through Cloudflare** (orange-cloud) and put the
  `/odusite/*` and `/web/image/*` paths behind a **Cloudflare Access**
  service-token policy — identical to topology A's Access step, reusing the same
  `CF_ACCESS_CLIENT_ID` / `CF_ACCESS_CLIENT_SECRET` secrets. This is the
  recommended option and gets you close to the tunnel's posture.
- **Or** a WAF custom rule / mutual TLS (authenticated origin pull) that only
  admits Cloudflare-originated, credentialed requests, plus rate limiting.
- **Or**, if your host supports it, a network ACL/firewall restricting inbound
  to your reverse proxy and dropping everything else.

Whatever you choose, keep the Odoo admin backend (`/web/login`, `/web/*`,
`/odoo`) off the public internet; the frontend only needs the API and image
routes.

---

## Which one?

| | A — Tunnel | B — Public origin |
|---|---|---|
| Odoo inbound ports | none | public HTTPS |
| Extra daemon | `cloudflared` | none |
| `ODOO_URL` | tunnel hostname | public Odoo URL |
| Edge lockdown | Access service token (recommended) | Access / WAF / mTLS (bring your own) |
| Best for | self-hosted / on-prem / private VPS | managed Odoo / Odoo.sh / already-public |

Both use the exact same Worker code and the same `CF_ACCESS_*` mechanism; only
`ODOO_URL` and how Odoo is exposed differ. See
[site-deploy.md](site-deploy.md) for the full site env/secret list and
[installation.md](installation.md) for the Odoo side.
