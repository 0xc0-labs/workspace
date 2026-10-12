# How we work

Part of the closed design ([the index](../design.md)): not reopened without
an explicit decision from the operator.

One orchestrator session in the workspace and one session per repo, instead
of one session in the workspace editing every repo (operator decision,
2026-10-10; workspace#74).

**Two roles.**

- **The orchestrator**: `claude -n orchestrator`, in the workspace. It plans,
  opens the issues, hands each repo its part, and checks what crosses repos.
  It edits the workspace repo (the design, the rules) and the board, and no
  other repo's files.
- **A repo session**: `claude -n <name>`, in that repo, opened by the operator
  in its own Herdr workspace when the repo is in play. It loads that repo's
  `CLAUDE.md`, plugins and permissions, works only there, and goes up to a
  draft PR.

A session's name is its repo's, as Herdr takes an agent's: dots to dashes, a
leading dot dropped (`github`, `offby1-cc`, `artistlabco-com`). The same name
goes to Herdr and to `claude -n`, and it is how the orchestrator addresses a
session. The operator works in Herdr: the workspace's own Herdr plugin
(`herdr/`, workspace#76) opens or focuses any repo's session, or the
orchestrator, from one key.

They talk through Claude Code's messages between local sessions. When a
repo's session is not open, the orchestrator starts the repo's autopilot
(below), which opens one session per Ready issue; it opens no other session
on its own.

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
  (`payload-19`, `github-61`). Given an issue, `work-issue` works that one and
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
  by priority. Two slots in the application repos; one in the others, whose
  merges end in applies that go in order (`herdr/autopilot.conf`). It never
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
  issue, gentle-ai spreads the work over its own subagents.
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
hooks and skills, with strict permissions. The application repos add
gentle-ai at workspace scope and the official plugins they need, and an
unattended session there may work up to a draft PR (operator decision,
2026-10-10). Inside an application repo, gentle-ai leads the work: its own
workflow plans, writes and reviews the code, with its receipt-driven review
on. `/0xc0:work-issue` is the interface between that repo and the
orchestrator: it starts from `main`, claims the issue on the board and takes
it as the contract, opens the draft PR by the org's rules, reports back, and
keeps its list of what a session never does (operator decision, 2026-10-11;
workspace#68). The cost is accepted: gentle-ai's reviewers spend more of the
subscription. For a change of medium or high risk, gentle-ai asks whether to
spend the time on a review. The question does not approve the change. A
session the autopilot starts grants it itself, on the operator's standing
decision (operator decision, 2026-10-12; workspace#117,
claude-config#57). A session opened by hand asks the operator in its tab.
Reviews are never turned off: one found three real spots in payload#29. The plugin carries no agents (operator decision, 2026-10-11;
workspace#78): each repo's session builds and checks its own changes, and
what a reviewer checked lives in that repo's docs (`infrastructure`'s
`docs/zones.md`, Invariants; `gitops`' `CLAUDE.md`, Before opening a PR).
gentle-ai's feature document, `odd/tasks/<feature>.md`, is versioned with
its feature, in the same PR (operator decision, 2026-10-12; workspace#98):
gentle-ai means it to be recoverable, and commits its own; Engram's copy is
on one laptop.

**What stays the operator's**: merging, every apply, writing and rotating
secrets, which repos' sessions are open, and pausing a repo's autopilot.

**Cost.** Every session draws on the operator's Claude subscription, and
several at work spend it faster than one: an autopilot's slots bound how
many of its sessions run at once. No `ANTHROPIC_API_KEY` in the environment
and no `--bare`, either of which bills the API instead.
