# 0xc0-labs — workspace

This directory is the clone of `0xc0-labs/workspace` and holds the other
repos of the organization as subdirectories. Each one is an independent git
repo with its own remote. **Never make a commit that crosses repos.**

Work runs as one orchestrator session here and one session per repo
(Sessions, below). This file reaches both: a session started in a repo loads
it too.

## Repos

| Directory        | Repo              | Contents                                        |
|------------------|-------------------|-------------------------------------------------|
| `.github/`       | `.github`         | org Terraform + reusable workflows              |
| `claude-config/` | `claude-config`   | marketplace and `0xc0` plugin (hooks, skills)   |
| `infrastructure/`| `infrastructure`  | Packer + OpenTofu + Ansible + docs              |
| `gitops/`        | `gitops`          | ArgoCD manifests: `bootstrap/prod/`, `platform/`, `apps/` |
| `vault/`         | `vault`           | OpenTofu configuration of the cluster's Vault   |
| `packages/`      | `packages`        | shared code as versioned npm packages (`@0xc0-labs/<name>`) |
| `offby1.cc/`     | `offby1.cc`       | Next.js landing page for offby1.cc              |
| `artistlabco.com/` | `artistlabco.com` | the artist's site and its Strapi, in `cms/`   |
| `matchmark/`     | `matchmark`       | Matchmark, the platform for applications made of AI agents; its design in `docs/` |
| `matchmark-config/` | `matchmark-config` | Matchmark's definitions for the org's own workspace |
| `matchmark-playground/` | `matchmark-playground` | the repo Matchmark's factory opens its pull requests in; nothing of value lives there |
| `app-*/`         | various           | applications                                    |

Dependency order: `.github` → `infrastructure` → `gitops` → `vault` →
`packages` → the applications (`offby1.cc`, `artistlabco.com`, `matchmark`,
`app-*`), which pin its packages. `matchmark-config` comes after `matchmark`:
it holds definitions for the platform `matchmark` builds.
`matchmark-playground` comes after `matchmark` too: it is where the
platform's factory opens its pull requests.
`claude-config` stands apart: nothing depends on it at deploy time.
A downstream change is not merged until the upstream one is applied.

## Changes that cross repos

1. Plan mode first. List what each repo needs before editing anything.
2. One branch per repo, with the same name everywhere.
3. One PR per repo. In the body, link the sibling PRs and state the merge order.
4. `infrastructure` and `.github`: `main` only, PR required, apply behind manual
   approval. The human runs the apply, never you.

## Sessions

`docs/design/how-we-work.md` decides. In short:

- **Here: the orchestrator** (`claude -n orchestrator`). Plans, and opens each
  repo's issue with everything its session needs: the outcome, the acceptance
  criteria, the branch, the sibling issues and the merge order. Hands each repo
  its issue, and checks the whole set before calling it done: every PR's
  checks, the merge order, and what one repo does to another. Edits the
  board itself, but no file in its own session: a subagent in its own
  worktree implements each change to this repo and opens the PR (operator
  decision, 2026-10-12; workspace#126). It never edits another repo's
  files. After it sets a repo's issues Ready, starts that repo's autopilot:
  `herdr/bin/autopilot start <repo directory>`.
- **In a repo** (`claude -n <name>`). Works only that repo, from its issue,
  up to a draft PR, and reports back to the orchestrator: the PR, its checks,
  what it did not do, and any question. Anything that reaches past the repo
  goes back to the orchestrator, not done from here.
- Messages between sessions carry pointers and reports, never approvals: what
  is the operator's stays the operator's, whoever asks.
- **Names**: a session is named after its repo, as Herdr takes an agent's:
  dots to dashes, a leading dot dropped (`github`, `offby1-cc`,
  `artistlabco-com`); the workspace's is `orchestrator`. The orchestrator
  addresses a session by that name.
- **Opening one**: in Herdr, in its terminal app or its desktop app, the
  workspace's plugin or mod (`herdr/README.md`) opens or focuses a repo's
  session, or the orchestrator, from one key.
- **The autopilot** (`herdr/README.md`), started by the orchestrator, or by
  the operator from another key: it starts one session per Ready issue,
  named `<name>-<n>` (`gitops-19`), each in its own worktree under
  `.worktrees/`, which works that issue and ends, and turns itself off when
  nothing is left. The operator pauses a repo from the key; an issue to leave
  alone is Blocked.

## Tracking — mandatory

The org project board, `0xc0-labs` (`github.com/orgs/0xc0-labs/projects/1`),
is the source of truth for the state of work, every repo's, `artistlabco.com`
included (operator decision, 2026-10-10: its own project, #3, is closed). It
is private. **No work starts without an issue on it.**

1. Before editing anything, find the issue for the task, or open one in the
   repo it belongs to and add it to the board.
2. Move it to `In Progress` when you start, `Blocked` when it waits on
   something outside the task.
3. Every PR body links it: `Closes #N`, or `Refs owner/repo#N` from a sibling
   repo. A PR without a linked issue fails the `issue` check, unless one of
   the org's GitHub Apps opened it (`0xc0-labs-promoter`,
   `0xc0-labs-renovate`): no person can open a PR as an App.
4. It closes through the PR that finishes it, not by hand.

How an issue is written and filed, so the board filters without labels:

| What | Where |
|---|---|
| Title | What must be true, or the problem, in a plain sentence: "Runners register without the App key on disk", "Every vault PR's plan fails with a 403". No type prefix and no repo: both are fields. The PR that closes it carries the Conventional Commit, written for the change it makes, and its branch follows from that (operator decision, 2026-10-10). |
| Kind of work | The org's issue type: Feature, Bug or Task. |
| Repo | The board's `Repository` field: `repo:0xc0-labs/artistlabco.com` is that site's work. Keep the column visible in table views: sibling sub-issues can read alike. |
| Order | `Priority`: P1 now, P2 next, P3 some day. |
| State | `Status`: Todo (written down, maybe incomplete or waiting), **Ready** (a complete contract, and what it depends on is applied: a repo session may take it), In Progress (taken: moving it here is the claim), Blocked, Done. |
| A change across repos | A parent issue in the workspace with the outcome, and one sub-issue per repo, each closed by its own repo's PR. Their order is GitHub's "blocked by" between sub-issues: one turns Ready only once what blocks it is closed. |
| Anything else related | GitHub's "relates to": a follow-up and the issue it came from, a fix and the change that caused it, the design behind an implementation. |

A request that arrives mid-conversation gets its issue first. The board is
loaded into every Claude Code session by the plugin's `SessionStart` hook;
`/project-status` reads it on demand. Decisions do not live on the board —
they stay in the design (`docs/design.md`, its index).

## Commits

Conventional Commits, in English, in every repo.

```
<type>(<scope>): <subject>
```

- Types: `feat`, `fix`, `docs`, `refactor`, `chore`, `ci`.
- Scope: the area touched — `firewall`, `zones`, `packer`, `ansible`, `tofu`,
  `compose`, `agents`, `hooks`. Optional, but use it when it is obvious.
- Subject: imperative, lowercase, no trailing period, 72 characters or less.
- `!` after the scope for any change that recreates a resource or breaks a
  contract (`feat(tofu)!: move vm-edge to its own vnet`). Explain it in the
  body.
- Body when the why is not obvious from the subject. Wrap at 72.

No trailers added by tooling: **never** `Co-Authored-By: Claude`, never a
generated-by footer. The commit is signed by whoever runs it.

## Branches and pull requests

Branch names mirror the commit types: `<type>/<slug>`.

```
feat/vault-transit-8200
fix/edge-bind-address
chore/bump-opentofu
docs/zone-matrix-rewrite
```

The same branch name in every repo the change touches, and only in those.

PRs are **squash merged**, so the PR title becomes the commit on `main`: write
it as a Conventional Commit subject, same rules as a commit message.

The PR body links the sibling PRs and states the merge order. No trailers
added by tooling: no generated-by footer, same rule as commits.

## Autonomy

Without asking: create branches, commit, push a branch, open issues, open a
**draft** PR, mark it ready once it can be merged (its checks green, its
review done, nothing left to do), and add items to the project board. A
draft is work in progress; a ready PR can be merged (workspace#119).

Ask first: merging, creating, renaming or deleting a repo, changing
organization settings, and anything that applies infrastructure. The apply
is launched by the human, always.

The rule behind it: work freely while nothing is final: a ready PR is a
proposal, and only the merge makes it final.

## Git identity

Every repo under `~/git/github/0xc0-homelab/` commits as
`sergioaten <me@sergioaten.cloud>`.

It is not set per repo. `gitconfig` in this repo holds the identity and the
shared defaults, and a single `includeIf` in `~/.gitconfig` points at it:

```gitconfig
[includeIf "gitdir:~/git/github/0xc0-homelab/"]
	path = ~/git/github/0xc0-homelab/workspace/gitconfig
```

The same file pins the SSH key: `core.sshCommand` uses `~/.ssh/0xc0-homelab`
with `IdentitiesOnly`, so git never offers another key to these remotes.
`core.excludesFile` points at `shared-excludes` in this repo, which holds the
excludes every repo shares (`.DS_Store`).

Scoping by path means a repo cloned later by `bootstrap.sh` gets the identity
with no extra step, and nothing outside this tree is affected. On a fresh
machine, that `includeIf` is the only thing to add by hand.

## Tooling

**Nothing is installed system-wide. Every tool comes from `mise`.**

No `brew install`, no `apt install`, no `npm -g`, no `pip install`, no
downloading a binary into `/usr/local/bin`. If a tool is missing, it gets
declared in the repo's `mise.toml` with a pinned version, and that is the fix.

- Each repo carries its own `mise.toml` and declares **everything** it needs,
  including tools the workspace also declares. A repo is cloned alone by CI,
  so it cannot lean on a parent config.
- Versions are pinned exactly. No `latest`, no version ranges.
- Bumping a version is its own commit: `chore(mise): bump opentofu to X.Y.Z`.
- Every repo commits a `mise.lock` (workspace#70): each tool's URL and
  checksum for `linux-x64` and `macos-arm64`, and its npm integrity under
  `.mise/locks/` for an `npm:` tool. `[settings] locked = true` in each repo
  refuses anything the lock does not cover; after any change to `[tools]`,
  `mise lock`. The workspace locks its own tools but sets no `locked`: its
  settings reach every repo under it.
- `mise.local.toml` is for personal overrides and is never committed.

## Claude Code plugins

Each repo enables in its own `.claude/settings.json` the plugins a session
started there needs: the workspace's settings do not reach a session started
inside a repo. Every repo enables `0xc0`, or its sessions run without the
org's hooks. From Anthropic's marketplace, only what applies (workspace#72):

| Plugin | Where |
|---|---|
| `claude-md-management` | the workspace |
| `typescript-lsp` | the TypeScript repos; `typescript-language-server` and `typescript` pinned in their `mise.toml` |
| `frontend-design` | the frontends |

`agent-skills` is not Anthropic's: it comes from the org's marketplace, as
`agent-skills@0xc0-labs`, and a repo enables it in its own
`.claude/settings.json` where it leads the work inside an issue:
`packages`, `artistlabco.com` and every new application repo (workspace#214).

`software-architecture` is the org's own, from the same marketplace:
hexagonal architecture, domain-driven design and REST API design, for a
session that designs or reviews application code. `packages` and every
application repo enable `software-architecture@0xc0-labs` (workspace#218).
Its skills name no framework or product, so a rule that holds for one
framework alone goes in the repo that uses it, in its `CLAUDE.md` or `docs/`.

On a machine, Claude Code loads a repo's enabled plugins only once they are
installed for its path, and a worktree uses its repo's record:
`herdr/bin/autopilot prepare`, which `bootstrap.sh` and every autopilot run,
installs whatever is missing, at local scope (workspace#106, #115), and
brings up to date the org's own plugins the repo enables (workspace#221).

Nothing that overlaps what is already there: `/simplify`, `/code-review` and
`/security-review` are built in. What leads the work inside an issue is the
repo's harness: `agent-skills` where its settings enable
`agent-skills@0xc0-labs` (from the org's marketplace, pinned there by tag and
commit; operator decision, 2026-11-17; workspace#214). The harness's feature
document is `spec/<feature>.md` (spec, plan and tasks in that one file: no
`SPEC.md`, no `tasks/`), committed in the same PR as its feature, never kept
out of git (workspace#98). Where a harness's instructions and the org's
differ, the org's win: this file, `docs/design/` and the skills of the org's
own plugins (`0xc0`, `software-architecture`).

Plugins keep themselves current (workspace#80):

- **Every repo's `.claude/settings.json` sets `"autoUpdate": true`** beside
  the `source` of each third-party marketplace it declares (`0xc0-labs`, and
  `hashicorp` in `infrastructure`). A third-party marketplace defaults to
  `false`, and a repo's entry overrides the user's whole, so it goes in each
  repo. Anthropic's own already defaults to `true`. The update is not at
  startup: after a session's first message, Claude Code waits a random delay
  of up to ten minutes, then updates the plugins on disk, and the session shows
  "Plugin updated: … Run /reload-plugins to apply". Each repo's install updates
  when a session started in that repo runs it, so the repo's checkout must be
  on an up-to-date `main`: a merged PR's stale branch may not carry the
  setting.
- **`agent-skills` is pinned in the org marketplace**, `claude-config`'s
  `.claude-plugin/marketplace.json`, by `ref` and `sha`. Moving it is one PR
  in `claude-config`, which reaches every repo through the `autoUpdate` of
  `0xc0-labs`: no `.claude/` commit in each. Why, in
  `docs/design/how-we-work.md`.
- **Any change under a plugin's directory bumps its `version` in
  `plugin.json`**, the only place it lives: a session gets a new copy only
  when the version changes. `claude-config`'s CI fails a PR that does not
  (`.github`'s `plugin-version` workflow).
- **A change to a repo's `.claude/` is committed by the operator.** A
  session's permission classifier refuses to commit its own Claude Code
  configuration, as self-modification: the session prepares the change and
  says so, the operator commits and pushes it.

## Documentation

Where a document belongs (operator decision, 2026-10-12; workspace#85):

1. **One home per fact**; everything else links to it. No text is copied
   between repos.
2. **This repo** holds what is the org's: the decisions with their reasons
   and dates (`docs/design.md` is their index), `docs/discarded.md`,
   `docs/accepted-risks.md`, how we work, and the common rules, here.
3. **Each repo** holds its own: how its part of the system is (`docs/`), how
   it is operated (its README: runbooks and the operator's commands), and the
   rules that apply there alone (its `CLAUDE.md`).
4. **A repo's `CLAUDE.md` never repeats a rule of this file**, which every
   session loads: it states only its own.
5. **An operator procedure lives in the repo that owns what it touches.**
   Writing a secret: the generic block once, in `vault`'s README; everything
   else links to it and names only which keys at which path.

## Rules that apply in every repo

- **Every application ships observable**: OTLP to
  `otel-gateway.opentelemetry.svc.cluster.local` (logs go on stdout instead,
  in the OpenTelemetry JSON line that `@0xc0-labs/observability` writes, which
  the node agent reads), and RUM when it has a frontend, through Faro
  (`initRum` in `@0xc0-labs/observability`). All in the same change that
  deploys it (`docs/design/platform.md`).
- **Everything written is in English**: file contents, file and directory
  names, code comments, commit messages, branch names, PR titles and bodies,
  docs. The conversation with the operator is in Spanish.
- **Comments say only what the code cannot** (operator decision, 2026-10-12;
  workspace#95): a non-obvious why, a constraint, an external quirk, or the
  issue or document that holds the reason. A descriptive name beats a
  comment. No comment says what the next line does, tells history (git and
  the PR hold it; at most a reference such as `(#204)`), or repeats a README
  or `docs/design.md`: it links to it. A why written nowhere else is never
  dropped: it stays, or moves to the README.
- No `tofu apply`, `tofu destroy` or `ansible-playbook` without `--check`.
- **Every workflow with steps of its own lives in `.github`**, as a reusable
  workflow (operator decision, 2026-09-29). Every other repo holds only thin
  callers: their triggers and paths, then
  `uses: 0xc0-labs/.github/.github/workflows/<name>.yml@main`. A new
  pipeline starts there, never in the repo that uses it.
- **Code that two repos need alike lives once**, as a versioned package in
  `0xc0-labs/packages`, published as `@0xc0-labs/<name>` and pinned by each
  app (operator decision, 2026-10-12; workspace#121). Extract when a second
  repo needs the same code, or a behaviour that must stay alike: observability,
  security headers, log format, health checks. Not code that only looks
  alike, a line or two, or configuration. The rest in
  `docs/design/delivery.md`.
- OpenTofu is **always** written as modules, with Google's layout:
  `modules/<name>/` for resources, `environments/<env>/` for roots, which only
  call modules. Each root has its own state key,
  `0xc0/<repo>/<environment>.tfstate` in RustFS, never a shared one. Full
  conventions in `.github/README.md`.
- Secrets live in Vault (`vault` repo, README), never in a repo, not even
  encrypted. A file holding sensitive material is a bug. The operator writes and
  rotates them; Claude writes policies and wiring, never a value.
- Before proposing any IP or subnet, check it against `zones`, `vms` and
  `containers` in `infrastructure/environments/prod/terraform.tfvars` and the
  reserved ranges in `infrastructure/docs/zones.md`, which are off limits.
- What is discarded stays discarded. The list and the reasons are in
  `docs/discarded.md`. Do not reopen it unless the human explicitly asks.
- **Semgrep runs in CI only.** A session never runs it on the machine: it
  reads the findings of the `semgrep / scan` job, in its job summary or with
  `gh run view <id> --log` (operator decision, 2026-10-12; workspace#155:
  seven sessions scanning at once saturated the machine's CPU).

## Status

The design is closed (`docs/design.md`). The org is bootstrapped: every repo
is created by `.github/environments/prod`, with its ruleset active, and every
change goes through a PR linked to an issue.

What runs today:

- **The nodes** (`pve-1`, `pve-2`), two Proxmox nodes in one cluster with no
  QDevice and no HA, run by `infrastructure` from its OpenTofu root
  (`environments/prod`). `pve-2` is the main node, with 2 votes: it runs every
  guest but the sandbox node and holds each zone's gateway, the SNAT and PBS.
  `pve-1`, with 1 vote, runs the sandbox node and carries the zones' bridges
  at layer 2 only. The zones (`mgmt`, `ci`, `platform`) are plain bridges over
  Hetzner vSwitches, not SDN; the zone firewall and each node's firewall on
  DROP come from the same root. Both nodes have their NVMe in RAID 1
  (workspace#285).
- **The base services**, in `ct-base-01`, an LXC on `pve-2` in `ci`
  (`10.10.1.30`): Traefik (the reverse proxy of the Proxmox UI, PBS and
  RustFS, not the cluster's ingress) and RustFS (the OpenTofu state), reached
  over WARP only. There is no Docker on the nodes.
- **The templates** every VM clones, baked by Packer from the official
  Debian and Rocky cloud images that OpenTofu imports.
- **The VMs outside the cluster**: `vm-access-01` and `vm-access-02`,
  identical cloudflared connectors of the admin tunnel (WARP); `vm-ci-01` and
  `vm-ci-02`, each with two ephemeral GitHub Actions runners, so CI runs
  inside the network and RustFS stays closed.
- **One RKE2 cluster** on Rocky Linux in `platform`, behind the HAProxy load
  balancers that also carry the public tunnel. ArgoCD deploys everything else
  in it from `gitops`. The `vm-lb` pair and the `vm-rke2` nodes are its VMs,
  in three pools, the label `0xc0.cc/pool` (workspace#288): `infra`, the three
  servers, with the shared services and their databases; `apps`, `vm-rke2-04`
  and `-05`, tainted, with every application; and `sandbox`, `vm-rke2-06` on
  `pve-1`, tainted, the one node that runs gVisor, for Matchmark's sandboxes
  (workspace#266). Longhorn keeps two replicas of each volume on data disks
  that live on `pve-2`'s SATA RAID 1, on every node but the sandbox node.
- **Vault** in the cluster, holding every secret. CI logs in with GitHub's
  OIDC token, one JWT role per repo, and no repo holds a secret or an Actions
  secret. The cluster's components read theirs through Vault Secrets
  Operator. Rotation is the operator's, by hand in Vault (.github#6).
- **How people sign in**: an operator is a member of the GitHub team
  `0xc0-labs/admins`, which also approves production applies beside the
  operator: the apply is still a human's. WARP enrolls by GitHub sign-in or a
  one-time PIN; Vault, Grafana, Argo CD, Headlamp and `kubectl` sign in
  through Cloudflare Access, with a personal client certificate valid 30 days
  as the cluster's fallback (`docs/design/platform.md`, Access for operators).
- **Prometheus, Loki, Tempo and Grafana** for metrics, logs and traces
  (workspace#290), behind one OpenTelemetry gateway, `otel-gateway`, that the
  applications and Traefik send OTLP to; a node agent reads the containers'
  logs. Loki and Tempo keep their data on R2. Grafana, at `grafana.int.0xc0.cc`
  over WARP only, holds the dashboards and the alerts, which reach nobody until
  a contact point is chosen. OpenObserve is gone. RUM goes through Faro, from
  `offby1.cc`, `artistlabco.com` and its CMS admin, into Loki through the
  gateway.
- **The applications**: the `offby1.cc` landing page and Mautic, from
  `gitops/apps/`; Plane, Matchmark's tracker (the org's work stays on the
  project board), reached over WARP only (0xc0-labs/workspace#247);
  Matchmark, with a gateway, a Temporal and a factory worker of its own,
  reached over WARP only (0xc0-labs/workspace#252, 0xc0-labs/workspace#255);
  each site's own Strapi, in `cms/` of its repo (`artistlabco.com`'s first;
  0xc0-labs/workspace#202). Every application repo carries the `app` topic.

Every VM carries `prevent_destroy`.
