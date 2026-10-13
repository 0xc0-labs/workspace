# Closed design — 0xc0-labs

Status: **closed**. Not reopened without an explicit decision from the operator.

The design records the org's decisions, each with its reasons, its date and
the issue it came from. It is split by subject; this file is its index. How
the pieces are and run is each repo's (below), and where a document belongs
is the rule in `CLAUDE.md`, Documentation.

## Decisions

| File | What it decides |
|---|---|
| [`design/network.md`](design/network.md) | Addressing and zones, the machines and why they are so, the transit between zones, the flows (web, TLS, public and internal names, admin, deploy, egress) |
| [`design/platform.md`](design/platform.md) | The stack: the node and its RAID, the cluster, ArgoCD, Vault, the ingress and WAF, observability, storage (Longhorn, R2), email, the data services (MariaDB, PostgreSQL), Mautic and Payload; Payload as the backend of every site, its capabilities generic and its secrets per tenant, and leads reaching Mautic through it (2026-10-13; workspace#168, #169); each capability switched on per tenant, off by default, and one Mautic per site that needs it, the shared one retired (2026-10-13; workspace#171); the templates |
| [`design/secrets.md`](design/secrets.md) | Where secrets live, how CI and the cluster read them, who writes them, what stays outside Vault |
| [`design/delivery.md`](design/delivery.md) | Repos and their policies; how an application ships: rc and release, a release on every push without staging, promotion, `gitops`' merge queue, where CI runs, staging, migrations, frontends as Payload's BFFs (2026-10-13; workspace#168, #169), observability, private images, the versioned contract, CI order gates, tests, shared packages, Renovate |
| [`design/how-we-work.md`](design/how-we-work.md) | The orchestrator and the repo sessions, the autopilot's one session per issue, plugins and permissions, what stays the operator's |
| [`discarded.md`](discarded.md) | What was considered and turned down, and why: not proposed again |
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
