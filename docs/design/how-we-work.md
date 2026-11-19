# How we work

Part of the closed design ([the index](../design.md)): not reopened without
an explicit decision from the operator.

One orchestrator session in the workspace and one session per repo, instead
of one session in the workspace editing every repo (operator decision,
2026-10-10; workspace#74).

**Two roles.**

- **The orchestrator**: `claude -n orchestrator`, in the workspace. It plans,
  opens the issues, hands each repo its part, and checks what crosses repos.
  It edits the board itself, the workspace repo (the design, the rules) only
  through a subagent in its own worktree, and no other repo's files.
- **A repo session**: `claude -n <name>`, in that repo, opened by the operator
  in its own Herdr workspace when the repo is in play. It loads that repo's
  `CLAUDE.md`, plugins and permissions, works only there, and goes up to a
  draft PR.

A session's name is its repo's, as Herdr takes an agent's: dots to dashes, a
leading dot dropped (`github`, `offby1-cc`, `artistlabco-com`). The same name
goes to Herdr and to `claude -n`, and it is how the orchestrator addresses a
session. The operator works in Herdr: the workspace's own Herdr plugin
(`herdr/`, workspace#76) opens or focuses any repo's session, or the
orchestrator, from one key, in Herdr's terminal app or in its desktop app.

They talk through Claude Code's messages between local sessions. When a
repo's session is not open, the orchestrator starts the repo's autopilot
(below), which opens one session per Ready issue; it opens no other session
on its own.

**Herdr is two products, and the integration serves both through one layer
with two backends** (operator decision, 2026-11-17; workspace#226, #232). The
terminal app (`herdr`, the TUI) and the desktop app (`herdr-app`) share no base:
the TUI has its own server, the app is a client of `herdr-core` (`hc`), a
terminal runtime that draws nothing and whose one published API promises only
to grow, and what runs in one does not show up in the other. Upgrading the TUI
brings no shared base, so as long as both are used the integration has to speak
to each. It is the layer `herdr/lib/frontend/`: `open-session` and `autopilot`
ask it for spaces, tabs and sessions, and its backend, `tui` or `app`,
translates; `pick` and the app's mod only run those two scripts. The desktop
app comes first where the work has to choose, and the `tui` backend stays as it
was, the way back while the app and its core, 0.1.x and self-updating, can
change under us. The app's backend talks to the core first: `hc` carries everything that is a session (creating, finding, reading,
knowing it ended), found by labels of ours; the window, `herdr-app`, is only
for focusing, naming and showing the picker, so an autopilot does not depend on
an open window. A repo never has two sessions or two autopilots: before it
creates one, a script looks in every front end that answers. The picker is one
mod in the app, one popup with both keys, where the TUI has two popups; the key
that opens it is the operator's, in their own `keys.json`. How it is done:
`herdr/README.md`.

**Repo sessions take their own work from the board.** One board for every
repo, `artistlabco.com` included (`CLAUDE.md`, Tracking, has how an issue is
filed). An issue turns **Ready** only with a complete contract and with what
it depends on applied: GitHub's "blocked by" orders the sub-issues of a change
across repos, and the orchestrator, or the operator, moves an issue to Ready
once its blockers are closed. Todo holds the rest. A repo session opened as
`claude -n <name> "/0xc0:work-issue"` takes its repo's Ready issue of highest
priority and moves it to In Progress, which is the claim; when it finishes
one, it looks for the next before it stops. A session acts only on a turn, so
one with nothing Ready waits, and the orchestrator, when it moves an issue to
Ready, messages that repo's session to look again. No session polls the board
on a timer: every look is a turn of the model, paid whether or not anything
is there. An issue set Ready by hand, past the orchestrator, is seen at the
session's next look.

**The autopilot: one fresh session per issue** (operator decision,
2026-10-12; workspace#103). A session that takes issue after issue carries
every earlier one in its context: each costs more of the subscription than
the last, the work gets worse, and the session keeps the rules and plugins it
loaded at its start. Nothing of an earlier issue helps the next: the contract
is the issue, the progress is the feature document and the PR, the rules are
the `CLAUDE.md` files. So a repo's issues run on its autopilot: the
orchestrator sets an issue Ready and starts the autopilot of its repo
(operator decision, 2026-10-12; workspace#107), which works the repo's Ready
issues one session each and turns itself off when nothing is left. The
operator can turn it on or off from a key too. A repo whose autopilot is off
works as above.

- **One session per issue.** The autopilot starts
  `claude -n <name>-<n> -w <name>-<n> "/0xc0:work-issue <repo>#<n>"`
  (`gitops-19`, `github-61`). Given an issue, `work-issue` works that one and
  ends, its last line `work-issue: done <repo>#<n>`, or `stopped` with the
  reason.
- **Unattended, up to a draft PR.** It runs in auto mode
  (`--permission-mode auto`; operator decision, 2026-10-12; workspace#111):
  a classifier approves routine commands and blocks risky ones, and the
  repo's `deny` rules still hold (no merge, no ready, no apply). The repo's
  allow list alone stopped it at every new command.
- **Its own worktree.** The `0xc0` plugin's worktree scripts, which the
  autopilot passes as the session's hooks, place it beside the repos, in the
  workspace's `.worktrees/<name>-<n>/`, detached at `origin/main`. Claude
  Code's default place is inside the repo. There, Node would resolve a module
  missing from the worktree in the primary clone's `node_modules`, and the
  primary clone's tools would walk into every worktree. Sessions of one repo
  work side by side without touching each other's files, and share the
  approvals saved in the primary clone.
- **The loop.** It runs in the `autopilot` tab of the repo's Herdr workspace.
  Every minute it closes the tab of each session that printed its last line,
  removes that session's worktree when nothing in it exists only there, and
  starts a session per free slot, on the Ready issues blocked by nothing open,
  by priority. Three slots in `matchmark`, two in the other application repos
  and in `packages`, one in the others, whose merges end in applies that go
  in order (`herdr/autopilot.conf`). It never
  closes a session that is working or waiting on the operator. Its look at
  the board is a script's, not a turn of the model: one small GraphQL query,
  one point of the GitHub API's 5,000 an hour, and none while every slot is
  busy. Once no session tab is left and nothing is Ready to start, it closes
  its own tab, so it never polls an empty board.
- **Holds live on the board.** An issue the operator wants left alone is
  Blocked. A repo is paused by turning its autopilot off from the key, which
  starts nothing more and lets the running sessions finish; the orchestrator
  starts it again at the next issue it sets Ready.
- **Never several sessions on one issue.** A big issue is split into
  sub-issues, which run side by side where none blocks another. Inside one
  issue, the repo's harness spreads the work over subagents: the three
  reviewers of `agent-skills`, in parallel (operator decision, 2026-11-17;
  workspace#214).
- Orca, which runs agents in worktrees too, was weighed and set aside
  (workspace#104). Herdr already runs the sessions. Orca's notifications to
  the phone go through its maker's servers, and its settings live outside any
  repo.

**The issue is the contract.** A repo session starts with no memory of the
conversation behind its task, so everything it needs is in its issue: the
outcome, the acceptance criteria, the branch name, the sibling issues and the
merge order. The orchestrator's message points at the issue and adds nothing
the issue lacks. The repo session answers with a short report: the PR, its
checks, what it could not do, and any question for the operator.

**The orchestrator owns integration.** A green PR in every repo is not a
working change. Before a set of PRs is called done, the orchestrator checks
all of them, their merge order, and what one repo does to another: a policy
another repo's plan needs, a setting a repo inherits from the workspace, a
hook a session lacks. Each of those slipped through on 2026-10-10 while every
PR on its own was green.

**A ready PR can be merged** (operator decision, 2026-10-12; workspace#119).
A session opens its PR as a draft, to see its checks while it works. It
marks the PR ready once its checks are green, its review is done and nothing
is left to do. A PR waiting on a `.claude/` patch the operator commits stays
a draft. The orchestrator reviews every ready PR. On a finding, it puts the
PR back to draft with a comment and sets the issue Ready again, so a new
session continues the same branch. So the operator merges what is ready, in
the merge order the orchestrator gave.

**Code two repos share is noticed before it is copied** (operator decision,
2026-10-12; workspace#121). It becomes a package in `0xc0-labs/packages`,
by the rule in [delivery](delivery.md). The orchestrator notices a candidate
when a contract it writes says "as in repo X", or when two issues in
different repos have the same outcome, and opens the extraction issue first.
A repo session that finds what it needs already in another repo names the
candidate in its report. The orchestrator, reviewing a set's PRs, notices
code duplicated across repos. It decides by the rule and writes the reason
on the issue, and asks the operator only when a package would change the
design.

**Plugins and permissions by kind of repo.** Every repo enables `0xc0` in its
own `.claude/settings.json`. The infrastructure repos (`.github`,
`infrastructure`, `gitops`, `vault`, `claude-config`) work with `0xc0`'s
hooks and skills, with strict permissions. The application repos add the
harness that leads the work inside an issue and the official plugins they
need, and an unattended session there may work up to a draft PR (operator
decision, 2026-10-10). The harness is `agent-skills` in `packages` and
`artistlabco.com`, and what every new application repo starts with;
`offby1.cc` carries none (operator decision, 2026-11-17; workspace#214).
What `agent-skills` replaced, and why, is in [discarded](../discarded.md).
Everything outside an issue stays the org's, whatever the harness: the
board, the autopilot, and `/0xc0:work-issue`. That skill is the interface
between a repo and the orchestrator, and the frame around the harness: it
starts from `main`, claims the issue on the board and takes it as the
contract, opens the draft PR by the org's rules, reports back, and keeps
its list of what a session never does (operator decision, 2026-10-11;
workspace#68). Where a harness's instructions and the org's differ, the
org's win, and the org's include the skills of its own plugins, `0xc0` and
`software-architecture` (operator decision, 2026-11-17; workspace#218). The
`0xc0` plugin carries no agents (operator decision, 2026-10-11;
workspace#78): each repo's session builds and checks its own changes, and
what a reviewer checked lives in that repo's docs (`infrastructure`'s
`docs/zones.md`, Invariants; `gitops`' `CLAUDE.md`, Before opening a PR).

**`agent-skills` leads the work inside an issue** (operator decision,
2026-11-17; workspace#214). It is Addy Osmani's Claude Code plugin,
`addyosmani/agent-skills` (MIT): skills for each step of a change (spec,
plan, incremental build, tests first, debugging, review, simplification),
reviewer agents, and commands that chain them. It registers no hook, starts
no MCP server, installs no binary and keeps no memory: what must outlive a
session is in the issue, the PR and the repo's files, the spec among them.
Its commands (`/spec`, `/plan`, `/build`, `/test`, `/review`, `/ship`,
`/code-simplify`, `/constraints`, `/webperf`) are the operator's to type, in
a session opened by hand: the plugin marks them `disable-model-invocation`,
so no session runs one by itself.

**The feature document is versioned with its feature**, in the same PR
(operator decision, 2026-10-12; workspace#98): a plan must be recoverable
from the repo, not kept on one laptop. With `agent-skills`, a Feature starts
with `spec/<feature>.md` (operator decision, 2026-11-17; workspace#214): the
spec, the plan and the task list in that one file, written with the plugin's
`spec-driven-development` and `planning-and-task-breakdown`. It is the first
commit of the Feature's branch, alone, as `docs(spec): plan <feature>`, and
`.github`'s `spec-first` fails a Feature PR whose first commit is not that
document. The skills' own defaults (`SPEC.md` at the root, `tasks/plan.md`,
`tasks/todo.md`) are not used: both skills yield to a project's convention,
and this is it. A Task or a Bug needs no document.

**No stop for approval** (operator decision, 2026-11-17; workspace#214).
`spec-driven-development` stops after the spec and asks the human to approve
it. In a session the issue is the approved requirement, and the spec is
reviewed with the PR. What the issue leaves open is a question on the issue,
not an assumption in the spec.

**The review before a PR is ready** (operator decision, 2026-11-17;
workspace#214). Three reviewers run in parallel on the branch's diff:
`agent-skills:code-reviewer`, `agent-skills:security-auditor` and
`agent-skills:test-engineer`. The session fixes and runs them again until
none returns a blocking finding:

| Reviewer | Blocking |
|---|---|
| `code-reviewer` | a finding it rates Critical or Required |
| `security-auditor` | a finding it rates Critical or High |
| `test-engineer` | a missing test it rates Critical or High, for behaviour the change adds or alters |

At most three rounds: a blocking finding still open after them, or one the
session holds wrong, leaves the PR a draft with the reason in its report,
for the orchestrator. The review applies to every PR that changes more than
documentation: one whose every file is `**/*.md`, `docs/**`, `.claude/**`
or `LICENSE`, what `.github`'s `changes` action already treats as no code,
runs none. The cost is accepted: three reviewers a round, on the subagents'
model (Sonnet). Reviews are never turned off: one found three real spots in
payload#29.

**Skills that yield to the org's rules** (operator decision, 2026-11-17;
workspace#214). Five of the plugin's skills cover what the org already
rules, and each repo that carries it denies them in its
`.claude/settings.json` (`Skill(agent-skills:<skill>)` in
`permissions.deny`):

| Skill | The org's rule instead |
|---|---|
| `git-workflow-and-versioning` | commits, branches and PRs: the workspace's `CLAUDE.md` |
| `ci-cd-and-automation` | every workflow lives in `.github` |
| `constraint-driven-development` | it interviews the operator and writes a `CONSTRAINTS.md`; a repo's rules are its `CLAUDE.md` |
| `documentation-and-adrs` | decisions live in the workspace's `docs/design` |
| `shipping-and-launch` | release and promotion: [delivery](delivery.md), and the operator |

**`software-architecture` is the org's own, and its skills name no product**
(operator decision, 2026-11-17; workspace#218). The plugin lives in
`claude-config` beside `0xc0`: three skills, `hexagonal-architecture`,
`domain-driven-design` and `rest-api-design`, which a session loads when it
designs or reviews application code. `packages` and every application repo
enable `software-architecture@0xc0-labs`, and a new application repo starts
with it: `packages` is no application, but what it publishes is application
code. The infrastructure repos do not load it. The skills name no
framework, CMS, SDK or vendor: they named Payload and Next.js about 140
times, and the move to a Strapi per site would have rewritten them, so they
serve any code, a site or a package, whatever the stack. A rule that holds
for one framework alone lives in the repo that uses it, in its `CLAUDE.md`
or `docs/`. Where one of its skills and a harness's differ, the org's skill
wins. The one case today is the error body of an endpoint the org writes:
`application/problem+json` (RFC 9457), where
`agent-skills:api-and-interface-design` shows `{ error: { code, message } }`,
because RFC 9457 is the standard. `rest-api-design` sets no pagination or
sorting convention: no RFC decides either, and one of its own would have been
a second answer beside the one `agent-skills` gives. It asks only for one
convention, the same on every list endpoint, and where `agent-skills` is
enabled, its convention is the one in use.

**The pin** (operator decision, 2026-11-17; workspace#214). The org
marketplace, `claude-config`'s `.claude-plugin/marketplace.json`, serves
`agent-skills` at a tag and its commit (`ref` and `sha`). Addy's own
marketplace is not used: pinning it pins only its catalogue, and its entry
installs the plugin's default branch. So third-party instructions reach a
session only at a commit the org chose. A repo only enables
`agent-skills@0xc0-labs`: moving the pin is one PR in `claude-config`, not a
`.claude/` commit in each repo, and it reaches every repo through the
`autoUpdate` of `0xc0-labs`. A new application repo starts with
`agent-skills@0xc0-labs` enabled, the five skills denied, and the
`spec-first` caller.

**What stays the operator's**: merging, every apply, writing and rotating
secrets, which repos' sessions are open, and pausing a repo's autopilot.

**Cost.** Every session draws on the operator's Claude subscription, and
several at work spend it faster than one: an autopilot's slots bound how
many of its sessions run at once. No `ANTHROPIC_API_KEY` in the environment
and no `--bare`, either of which bills the API instead.
