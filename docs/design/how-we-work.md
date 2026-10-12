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
repo's session is not open, the orchestrator asks the operator to open it;
it does not start one on its own.

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
writing and rotating secrets, and which repos' sessions are open.

**Cost.** Every session draws on the operator's Claude subscription, and
several at work spend it faster than one. No `ANTHROPIC_API_KEY` in the
environment and no `--bare`, either of which bills the API instead.
