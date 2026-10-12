# herdr

The workspace's [Herdr](https://herdr.dev) plugin, `0xc0-workspace`. One key
opens a repo's Claude Code session in its own Herdr workspace, or the
orchestrator. Another turns a repo's autopilot on or off: the autopilot
works the repo's Ready issues, one fresh session per issue, each in its own
tab and worktree, and turns itself off when nothing is left
(`docs/design/how-we-work.md`). The orchestrator starts it with
`bin/autopilot start <repo>` after it sets issues Ready.

## Autopilot

`bin/autopilot start <repo>`, or picking a repo from the key, gives the
repo's Herdr workspace an `autopilot` tab running `bin/autopilot run <repo>`,
which logs a line for everything it does. Every minute it:

1. closes the tab of each session that printed its last line,
   `work-issue: done <repo>#<n>` or `work-issue: stopped <repo>#<n>: <reason>`,
   and removes that session's worktree if it has no uncommitted changes and
   no commit missing from `origin`. Otherwise it keeps the worktree and says
   so. It never closes a session that is working or waiting on the operator;
2. starts one session per free slot, in a tab named after it, on the repo's
   Ready issues blocked by nothing open, by priority, then number:

   ```sh
   claude --permission-mode auto --settings .worktrees/.hooks.json \
     -n <name>-<n> -w <name>-<n> "/0xc0:work-issue <repo>#<n>"
   ```

   Auto mode lets the session work unattended: a classifier approves
   routine commands and blocks risky ones, and the repo's `deny` rules
   still hold.

   `.hooks.json`, which the autopilot writes, declares the `0xc0` plugin's
   worktree scripts from the workspace's `claude-config` checkout as the
   session's `WorktreeCreate` and `WorktreeRemove` hooks: they place the
   worktree at `.worktrees/<name>-<n>/` in the workspace, detached at
   `origin/main`. They come through `--settings` because Claude Code creates
   a `-w` worktree before it loads the plugins' hooks. If an issue's worktree
   is still there, kept from an earlier session, the autopilot leaves that
   issue alone and says so.

After a round with no session tab and nothing Ready to start, it closes its
own tab. A round that could not read the board, on a low API budget, does
not count.

`autopilot.conf` holds each repo's slots: two in the application repos, one
in the others. Picking the repo again, or closing the `autopilot` tab, turns
it off: nothing more starts, and the running sessions finish in their tabs.
To hold one issue, set it Blocked on the board. An issue it started once is
not started again until it is turned off and on, even if its session left it
Ready.

Its look at the board is one GraphQL query, one point of the GitHub API's
hourly 5,000, made only when a slot is free. Below 500 points left, it starts
nothing until the budget resets.

`bin/autopilot run <repo> --dry-run` prints one round, what it would close,
remove and start, changing nothing.

## Opening a session by hand

Pick a repo, and a tab named after it opens in its Herdr workspace, or a new
workspace, with `claude -n <name> "/0xc0:work-issue"`: the session takes that
repo's Ready issue of highest priority, and the next when it finishes. Pick
the workspace, and the orchestrator opens: `claude -n orchestrator`. A
session already open is focused, not opened twice.

## Names

A repo's name is its own as Herdr takes an agent's (`[a-z][a-z0-9_-]`): dots
to dashes, a leading dot dropped. An issue's session adds the issue's number.
The same name goes to Herdr and to `claude -n`, so the orchestrator finds a
session by it.

| Directory | Repo's workspace and session | An issue's session |
|---|---|---|
| the workspace | `orchestrator` | |
| `.github` | `github` | `github-61` |
| `offby1.cc` | `offby1-cc` | `offby1-cc-27` |
| `artistlabco.com` | `artistlabco-com` | `artistlabco-com-5` |
| any other repo | its name | `payload-19` |

## Setting it up, once per machine

`bootstrap.sh` links the plugin in place, so a change here reaches Herdr
with no reinstall. It installs each repo's enabled Claude Code plugins for
its path, which its worktrees' sessions need too. It has mise trust every
config under `~/git/github/0xc0-homelab/`, so a new worktree's `mise.toml`
asks for no `mise trust`, and creates `.worktrees/`.

The keys go in your own Herdr `config.toml` (`prefix+a` and `prefix+shift+a`
are free in the defaults), then `prefix+shift+r` reloads it:

```toml
[[keys.command]]
key = "prefix+a"
type = "plugin_action"
command = "0xc0-workspace.open-session"
description = "Open a repo session"

[[keys.command]]
key = "prefix+shift+a"
type = "plugin_action"
command = "0xc0-workspace.autopilot"
description = "Turn a repo's autopilot on or off"
```

## Files

```
herdr-plugin.toml   the actions and their popups
autopilot.conf      each repo's slots
bin/open-picker     an action: opens a popup
bin/pick            the popups: the workspace and every repo cloned in it
bin/open-session    opens or focuses one directory's session
bin/autopilot       the autopilot: its loop, and starting or toggling it
```

`bin/open-session <dir> --dry-run` prints what it would do, touching
nothing. Both scripts need `python3`, from the OS: `open-session` to read
Herdr's answers, and `autopilot` is written in it. The autopilot runs `gh`
through mise, from the workspace's `mise.toml`.
