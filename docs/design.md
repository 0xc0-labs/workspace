# Closed design — 0xc0-labs

Status: **closed**. Not reopened without an explicit decision from the operator.

The design records the org's decisions, each with its reasons, its date and
the issue it came from. It is split by subject; this file is its index. How
the pieces are and run is each repo's (below), and where a document belongs
is the rule in `CLAUDE.md`, Documentation.

## Decisions

| File | What it decides |
|---|---|
| [`design/network.md`](design/network.md) | Addressing and zones, the machines and why they are so, the transit between zones, the flows (web, TLS, public and internal names, admin, deploy, egress); a front's staging, and a site's CMS admin, published behind Cloudflare Access for people without WARP (2026-10-13; workspace#176; 2026-10-21; workspace#203) |
| [`design/platform.md`](design/platform.md) | The stack: the node and its RAID, the cluster, ArgoCD, Vault, the ingress and WAF, observability, storage (Longhorn, R2), email, the data services (MariaDB, PostgreSQL), Mautic and Strapi; **one Strapi per site, in the site's repo**, in place of the multi-tenant Payload of 2026-10-09 (workspace#64) (2026-10-20; workspace#203); its admin public behind Cloudflare Access, and its integrations' keys set in the admin and written to Vault by Strapi (2026-10-21; workspace#203); the admin built for the people who edit (2026-10-21; workspace#203). Decided for Payload and carried to each site's Strapi: the whole backend of a site, its capabilities generic, and leads reaching Mautic through it (2026-10-13; workspace#168, #169); each capability taken from a plugin, reused from Strapi or its community or one of ours, the site's `cms/` holding only its own (2026-10-21; workspace#202); one Mautic per site that needs it, the shared one retired, and the per-tenant switch of capabilities gone with the tenants (2026-10-13; workspace#171; 2026-10-20; workspace#203); capabilities stand alone, plans only narrow who gets in (2026-10-16; workspace#184); a membership says who belongs, never who pays, and a gated record names its audience (2026-10-18; workspace#197); each site's integrations configured in its admin, its keys in Vault written by Strapi, its storage and egress (2026-10-17; workspace#187); each site bringing its own provider accounts, the platform's own integrations built only when sites pay for them (2026-10-17; workspace#187); **Plane, Matchmark's tracker, not the org's**: WARP only and never public, its database on the shared PostgreSQL, its Valkey, RabbitMQ and object store its chart's in its own namespace, which enforces `baseline` and not `restricted` (2026-11-18; workspace#247); **Plane, the exception to every application being observable**: only the logs and the route and pod metrics the cluster takes of everything, no traces and no RUM (2026-11-19; workspace#250); **Matchmark, one application with a gateway of its own**: its names and their listener, its agentgateway and the Argo CD project that admits its cluster-scoped kinds, its database on the shared PostgreSQL, its artifacts in a RustFS of its own, its Transit key made by hand (2026-11-19; workspace#252); **Matchmark's Temporal and factory worker**: Temporal in the application's namespace as a second Application, its two databases on the shared PostgreSQL with no pooler, the worker running the operator's agents on their Claude subscription, and the gateway answering over WARP under the API's name (2026-11-19; workspace#255); the templates |
| [`design/secrets.md`](design/secrets.md) | Where secrets live, how CI and the cluster read them, who writes them, what stays outside Vault |
| [`design/delivery.md`](design/delivery.md) | Repos and their policies, Matchmark's two repos, `matchmark` and `matchmark-config`, with its design in `matchmark/docs/` (2026-11-18; workspace#244); how an application ships: rc and release, a release on every push without staging, Matchmark's until its console exists (2026-11-19; workspace#252), promotion, `gitops`' merge queue, where CI runs, staging, an application deployed once per site (2026-10-13; workspace#171), a second image built from a subdirectory and released with its repo's one version (2026-10-20; workspace#203), an application with one image per service and none named after its repo, taken by the release workflows with `own-image: false` (2026-11-19; workspace#252; .github#201), migrations, frontends as BFFs of their CMS (2026-10-13; workspace#168, #169), observability, private images, the versioned contract of a backend in its own repo, which Payload's retires with it (2026-10-20; workspace#203), CI order gates, a Python repo's checks with `python-check` (2026-11-19; .github#199), tests, shared packages, Strapi's plugins in a package from the start (2026-10-21; workspace#202), Renovate |
| [`design/how-we-work.md`](design/how-we-work.md) | The orchestrator and the repo sessions, the autopilot's one session per issue, plugins and permissions, **`agent-skills` leading the work inside an issue**, with its feature document, its review, its skills that yield and its pin (2026-11-17; workspace#214), the org's own `software-architecture` plugin: where it is enabled, its skills naming no product and winning where a harness's differ (2026-11-17; workspace#218), **Herdr's two front ends, the terminal app and the desktop app, served by one layer with two backends** (2026-11-17; workspace#226, #232), what stays the operator's |
| [`discarded.md`](discarded.md) | What was considered and turned down, and why: not proposed again; the multi-tenant Payload as every web's backend (2026-10-20; workspace#203); what led the work inside an issue, replaced by `agent-skills`, and `addyosmani/factory` (2026-11-17; workspace#214); the two exceptions to the object store in the cluster: Plane's attachments, because Plane signs uploads with a presigned POST and R2 does not (2026-11-18; workspace#247), and Matchmark's artifacts, for this application, for now (2026-11-19; workspace#252, #253) |
| [`accepted-risks.md`](accepted-risks.md) | The risks taken knowingly |

## How it is: each repo's own docs

- **The node, zones, addresses, VMs, templates, traffic and backups:**
  [`infrastructure/docs/architecture.md`](https://github.com/0xc0-labs/infrastructure/blob/main/docs/architecture.md),
  with diagrams, and
  [`infrastructure/docs/zones.md`](https://github.com/0xc0-labs/infrastructure/blob/main/docs/zones.md),
  port by port and its invariants.
- **Secrets, paths and the values the operator writes:** the
  [`vault` README](https://github.com/0xc0-labs/vault/blob/main/README.md).
- **What runs in the cluster, and each application's operation:** `gitops`'
  `CLAUDE.md` and the READMEs under `apps/` and `platform/`.
- **The org, its repos and the reusable workflows:** the
  [`.github` README](https://github.com/0xc0-labs/.github/blob/main/README.md).
- **Each application:** its own README.
