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
| [`design/platform.md`](design/platform.md) | The stack: the node and its RAID, the cluster, ArgoCD, Vault, the ingress and WAF, observability, storage (Longhorn, R2), email, the data services (MariaDB, PostgreSQL), Mautic and Strapi; **one Strapi per site, in the site's repo, in place of the multi-tenant Payload** (2026-10-20; workspace#203), replacing Payload as one multi-tenant instance, now replaced (2026-10-09; workspace#64); its admin public behind Cloudflare Access, and its integrations' keys set in the admin and written to Vault by Strapi (2026-10-21; workspace#203); the admin built for the people who edit (2026-10-21; workspace#203). Decided for Payload and carried to each site's Strapi: the whole backend of a site, its capabilities generic, and leads reaching Mautic through it (2026-10-13; workspace#168, #169); one Mautic per site that needs it, the shared one retired (2026-10-13; workspace#171), whose per-tenant switch of capabilities is replaced; capabilities stand alone, plans only narrow who gets in (2026-10-16; workspace#184); a membership says who belongs, never who pays, and a gated record names its audience (2026-10-18; workspace#197); each site's integrations configured in its admin, its keys in Vault written by Strapi, its storage and egress (2026-10-17; workspace#187); each site bringing its own provider accounts, the platform's own integrations built only when sites pay for them (2026-10-17; workspace#187); the templates |
| [`design/secrets.md`](design/secrets.md) | Where secrets live, how CI and the cluster read them, who writes them, what stays outside Vault |
| [`design/delivery.md`](design/delivery.md) | Repos and their policies; how an application ships: rc and release, a release on every push without staging, promotion, `gitops`' merge queue, where CI runs, staging, an application deployed once per site (2026-10-13; workspace#171), a second image built from a subdirectory and released with its repo's one version (2026-10-20; workspace#203), migrations, frontends as BFFs of their CMS (2026-10-13; workspace#168, #169), observability, private images, the versioned contract of a backend in its own repo, which Payload's retires with it (2026-10-20; workspace#203), CI order gates, tests, shared packages, a Strapi capability moving to a package when a second site needs it (2026-10-20; workspace#203), Renovate |
| [`design/how-we-work.md`](design/how-we-work.md) | The orchestrator and the repo sessions, the autopilot's one session per issue, plugins and permissions, what stays the operator's |
| [`discarded.md`](discarded.md) | What was considered and turned down, and why: not proposed again; the multi-tenant Payload as every web's backend (2026-10-20; workspace#203) |
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
