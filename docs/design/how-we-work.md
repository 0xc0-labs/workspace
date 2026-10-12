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
- **A repo session**: one per issue, in its own worktree, started by the
  repo's autopilot (below). It loads that repo's `CLAUDE.md`, plugins and
  permissions, works that one issue only there, goes up to a draft PR,
  reports, and ends.

A repo's name is its own as Herdr takes an agent's: dots to dashes, a leading
dot dropped (`github`, `offby1-cc`, `artistlabco-com`); an issue's session
adds the issue's number (`payload-19`, `github-61`). The same name goes to
Herdr, to `claude -n` and to `-w`, and it is how the orchestrator addresses a
session. The operator works in Herdr: the workspace's own Herdr plugin
(`herdr/`, workspace#76) turns a repo's autopilot on or off from one key, and
opens a repo's session by hand, or the orchestrator, from another.

They talk through Claude Code's messages between local sessions. When a
repo's autopilot is off, the orchestrator asks the operator to turn it on;
it starts no session on its own.

**Repo sessions take their own work from the board.** One board for every
repo, `artistlabco.com` included (`CLAUDE.md`, Tracking, has how an issue is
filed). An issue turns **Ready** only with a complete contract and with what
it depends on applied: GitHub's "blocked by" orders the sub-issues of a change
across repos, and the orchestrator, or the operator, moves an issue to Ready
once its blockers are closed. Todo holds the rest. The repo's autopilot starts
a session on each Ready issue blocked by nothing open, and the session moves
it to In Progress, which is the claim. No session polls the board: every look
would be a turn of the model, paid whether or not anything is there. The
autopilot's look is a script's, so an issue set Ready, by the orchestrator or
by hand, is taken within a minute.

**One session per issue** (operator decision, 2026-10-12; workspace#103). A
session that takes issue after issue carries every earlier one in its context:
each costs more of the subscription than the last, the work gets worse, and
the session keeps the rules and plugins it loaded at its start. Nothing of an
earlier issue helps the next: the contract is the issue, the progress is the
feature document and the PR, the rules are the `CLAUDE.md` files. So a
session works one issue and ends, its last line `work-issue: done <repo>#<n>`,
or `stopped` with the reason.

- **Its own worktree.** Each session runs in a Claude Code worktree,
  `claude -n <name>-<n> -w <name>-<n> "/0xc0:work-issue <repo>#<n>"`. The
  `0xc0` plugin's worktree scripts, which the autopilot passes as the
  session's hooks, place it beside the repos, in the workspace's
  `.worktrees/<name>-<n>/`, detached at `origin/main`. Claude Code's default
  place is inside the repo. There, Node would resolve a module missing from
  the worktree in the primary clone's `node_modules`, and the primary clone's
  tools would walk into every worktree. Sessions of one repo work side by side
  without touching each other's files, and share the approvals saved in the
  primary clone.
- **The autopilot.** One per repo, which the operator turns on or off from a
  key; it runs in the `autopilot` tab of the repo's Herdr workspace. Every
  minute it closes the tab of each session that printed its last line, removes
  that session's worktree when nothing in it exists only there, and starts a
  session per free slot, on the Ready issues blocked by nothing open, by
  priority. Two slots in the application repos; one in the others, whose
  merges end in applies that go in order (`herdr/autopilot.conf`). It never
  closes a session that is working or waiting on the operator. Its look at the
  board is one small GraphQL query, one point of the GitHub API's 5,000 an
  hour, and none while every slot is busy.
- **Holds live on the board.** An issue the operator wants left alone is
  Blocked. A repo is paused by turning its autopilot off, which starts
  nothing more and lets the running sessions finish.
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
workspace#68). The cost is accepted: gentle-ai's review asks the operator's
consent in the session's tab for a change of medium or high risk, so those
sessions are not wholly unattended, and its reviewers spend more of the
subscription. The plugin carries no agents (operator decision, 2026-10-11;
workspace#78): each repo's session builds and checks its own changes, and
what a reviewer checked lives in that repo's docs (`infrastructure`'s
`docs/zones.md`, Invariants; `gitops`' `CLAUDE.md`, Before opening a PR).
gentle-ai's feature document, `odd/tasks/<feature>.md`, is versioned with
its feature, in the same PR (operator decision, 2026-10-12; workspace#98):
gentle-ai means it to be recoverable, and commits its own; Engram's copy is
on one laptop.

**What stays the operator's**: marking a PR ready, merging, every apply,
writing and rotating secrets, and which repos' autopilots are on.

**Cost.** Every session draws on the operator's Claude subscription, and
several at work spend it faster than one: the autopilot's slots bound how
many run at once. No `ANTHROPIC_API_KEY` in the environment and no `--bare`,
either of which bills the API instead.
