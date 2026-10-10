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
| `offby1.cc/`     | `offby1.cc`       | Next.js landing page for offby1.cc              |
| `payload/`       | `payload`         | Payload CMS, multi-tenant backend of the fronts |
| `app-*/`         | various           | applications                                    |

Dependency order: `.github` → `infrastructure` → `gitops` → `vault` →
`offby1.cc`, `payload` and `app-*`.
A downstream change is not merged until the upstream one is applied.

## Changes that cross repos

1. Plan mode first. List what each repo needs before editing anything.
2. One branch per repo, with the same name everywhere.
3. One PR per repo. In the body, link the sibling PRs and state the merge order.
4. `infrastructure` and `.github`: `main` only, PR required, apply behind manual
   approval. The human runs the apply, never you.

## Sessions

`docs/design.md`, How we work, decides. In short:

- **Here: the orchestrator** (`claude -n orchestrator`). Plans, and opens each
  repo's issue with everything its session needs: the outcome, the acceptance
  criteria, the branch, the sibling issues and the merge order. Hands each repo
  its issue, and checks the whole set before calling it done: every PR's
  checks, the merge order, and what one repo does to another. Edits only this
  repo and the board, never another repo's files. When a repo's session is
  not open, asks the operator to open it.
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
- **Opening one**: in Herdr, the workspace's plugin (`herdr/README.md`) opens
  or focuses a repo's session, or the orchestrator, from one key.

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
   repo. A PR without a linked issue fails the `issue` check.
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
they stay in `docs/design.md`.

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
**draft** PR, and add items to the project board.

Ask first: marking a PR ready for review, merging, creating, renaming or
deleting a repo, changing organization settings, and anything that applies
infrastructure. The apply is launched by the human, always.

The rule behind it: work freely while nothing is presented as final.

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

Nothing that overlaps what is already there: `/simplify`, `/code-review` and
`/security-review` are built in, and the app repos carry gentle-ai.

Plugins keep themselves current (workspace#80):

- **Every repo's `.claude/settings.json` sets `"autoUpdate": true`** beside
  the `source` of each third-party marketplace it declares (`0xc0-labs`, and
  `hashicorp` in `infrastructure`): Claude Code then updates their plugins in
  the background at session start. A third-party marketplace defaults to
  `false`, and a repo's entry overrides the user's whole, so it goes in each
  repo. Anthropic's own already defaults to `true`. A session already open
  takes an update with `/reload-plugins`.
- **Any change under a plugin's directory bumps its `version` in
  `plugin.json`**, the only place it lives: a session gets a new copy only
  when the version changes. `claude-config`'s CI fails a PR that does not
  (`.github`'s `plugin-version` workflow).
- **A change to a repo's `.claude/` is committed by the operator.** A
  session's permission classifier refuses to commit its own Claude Code
  configuration, as self-modification: the session prepares the change and
  says so, the operator commits and pushes it.

## Rules that apply in every repo

- **Every application ships observable**: logs, metrics and traces to
  OpenObserve, and RUM when it has a frontend, in the same change that deploys
  it (`docs/design.md`, Stack).
- **Everything written is in English**: file contents, file and directory
  names, code comments, commit messages, branch names, PR titles and bodies,
  docs. The conversation with the operator is in Spanish.
- No `tofu apply`, `tofu destroy` or `ansible-playbook` without `--check`.
- **Every workflow with steps of its own lives in `.github`**, as a reusable
  workflow (operator decision, 2026-09-29). Every other repo holds only thin
  callers: their triggers and paths, then
  `uses: 0xc0-labs/.github/.github/workflows/<name>.yml@main`. A new
  pipeline starts there, never in the repo that uses it.
- OpenTofu is **always** written as modules, with Google's layout:
  `modules/<name>/` for resources, `environments/<env>/` for roots, which only
  call modules. Each root has its own state key,
  `0xc0/<repo>/<environment>.tfstate` in RustFS, never a shared one. Full
  conventions in `.github/README.md`.
- Secrets live in Vault (`vault` repo, README), never in a repo, not even
  encrypted. A file holding sensitive material is a bug. The operator writes and
  rotates them; Claude writes policies and wiring, never a value.
- Before proposing any IP or subnet, check it against `zones` and `vms` in
  `infrastructure/environments/prod/terraform.tfvars` and the reserved ranges
  in `infrastructure/docs/zones.md`, which are off limits.
- What is discarded stays discarded. The list and the reasons are in
  `docs/design.md`. Do not reopen it unless the human explicitly asks.

## Status

The design is closed (`docs/design.md`). The org is bootstrapped: every repo
is created by `.github/environments/prod`, with its ruleset active, and every
change goes through a PR linked to an issue.

What runs today:

- **The node** (`pve-1`), run by `infrastructure` from its OpenTofu root
  (`environments/prod`): the SDN zones (`mgmt`, `ci`, `platform`), the zone
  firewall, and the node's firewall on DROP. Traefik on the node (the host's
  reverse proxy, not the cluster's ingress) is reached over WARP only.
- **The templates** every VM clones, baked by Packer from the official
  Debian and Rocky cloud images that OpenTofu imports.
- **The VMs outside the cluster**: `vm-access-01` and `vm-access-02`,
  identical cloudflared connectors of the admin tunnel (WARP); `vm-ci-01` and
  `vm-ci-02`, each with two ephemeral GitHub Actions runners, so CI runs
  inside the network and RustFS stays closed.
- **One RKE2 cluster** on Rocky Linux in `platform`, behind the HAProxy load
  balancers that also carry the public tunnel. ArgoCD deploys everything else
  in it from `gitops`. The `vm-lb` pair and the `vm-rke2` nodes are its VMs.
- **Vault** in the cluster, holding every secret. CI logs in with GitHub's
  OIDC token, one JWT role per repo, and no repo holds a secret or an Actions
  secret. The cluster's components read theirs through Vault Secrets
  Operator. Rotation is the operator's, by hand in Vault (.github#6).
- **OpenObserve** for logs, metrics and traces, fed by the OpenTelemetry
  Operator's collectors.
- **The applications**: the `offby1.cc` landing page, Mautic and Payload
  CMS, from `gitops/apps/`. Every application repo carries the `app`
  topic.

Every VM carries `prevent_destroy`.
