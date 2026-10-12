# herdr

The workspace's [Herdr](https://herdr.dev) plugin, `0xc0-workspace`. One key
opens a repo's Claude Code session in its own Herdr workspace, or the
orchestrator. Another turns a repo's autopilot on or off: the autopilot
works the repo's Ready issues, one fresh session per issue, each in its own
tab and worktree, and turns itself off when nothing is left
(`docs/design/how-we-work.md`). The orchestrator starts it with
`bin/autopilot start <repo>` after it sets issues Ready.

Herdr also runs one third-party plugin the workspace installs, the file
viewer (File viewer, below).

## Autopilot

`bin/autopilot start <repo>`, or picking a repo from the key, gives the
repo's Herdr workspace an `autopilot` tab running `bin/autopilot run <repo>`,
which logs a line for everything it does. It first gets the repo's clone
ready, as `bin/autopilot prepare <repo>` does:

- it clones the repo into the workspace if it is missing. The clone stays:
  its path holds every worktree session's plugin records, memory and
  approvals;
- it moves the clone to an up-to-date `main`, from a branch origin no longer
  has and with nothing uncommitted. A branch origin still has, or uncommitted
  work, is someone's: it leaves it and says so;
- it installs the plugins the repo enables that have no record for its path,
  and updates `0xc0`, which Claude Code would otherwise update only after a
  session had started on the old one;
- it trusts the clone in Claude Code, as accepting "Do you trust the files
  in this folder?" there would: `hasTrustDialogAccepted` for its path in
  `~/.claude.json`, or `$CLAUDE_CONFIG_DIR/.claude.json`. A repo the org
  added later had no such record, so its first session, or its autopilot's
  first, stopped at that dialog until the operator accepted it by hand, and
  the org's repos are trusted (operator decision, 2026-10-12; #136). It
  trusts only a clone whose origin is in `0xc0-labs`, the workspace
  included, and its worktree sessions run on its entry. A clone already
  trusted leaves the file untouched; otherwise it sets that flag alone,
  under Claude Code's own lock on the file (`.claude.json.lock`), through a
  temporary file renamed over it, since running sessions write it too.

Then, every minute, it:

1. closes the tab of each session that printed its last line,
   `work-issue: done <repo>#<n>` or `work-issue: stopped <repo>#<n>: <reason>`,
   and removes that session's worktree if it has no uncommitted changes and
   no commit missing from `origin`. A branch GitHub deleted when its PR
   merged counts as on `origin` if that PR holds the worktree's last commit,
   since a squash merge puts its commits in `main` under other SHAs (#134).
   Otherwise it keeps the worktree and says so. It never closes a session that is working or waiting on the operator;
2. starts one session per free slot, in a tab named after it, on the repo's
   Ready issues blocked by nothing open, by priority, then number:

   ```sh
   claude --permission-mode auto --settings .worktrees/.hooks.json \
     -n <name>-<n> -w <name>-<n> "/0xc0:work-issue <repo>#<n>"
   ```

   Right before it starts a session, the autopilot moves the issue to In
   Progress on the board (`gh project item-edit`, by the issue's URL), so the
   claim does not depend on the session's own step (#161). If the move fails,
   the session is not started in that round and the next retries it. The
   `work-issue` skill keeps its own claim step for sessions started by hand.

   A round that starts a session updates `0xc0` first, once: a session
   loads the plugin on disk when it starts, and Claude Code's own update
   reaches only the next session (#124). Autopilots take turns at it
   under a lock in `~/.cache/0xc0/`, and skip the marketplace update when
   another did it under two minutes ago (#132).

   Auto mode lets the session work unattended: a classifier approves
   routine commands and blocks risky ones, and the repo's `deny` rules
   still hold.

   Each session runs with `OXC0_AUTOPILOT=1`, so the `0xc0` plugin's board
   hook skips the whole-board read it does not need (claude-config#71).

   `.hooks.json`, which the autopilot writes, declares the `0xc0` plugin's
   worktree scripts from the workspace's `claude-config` checkout as the
   session's `WorktreeCreate` and `WorktreeRemove` hooks: they place the
   worktree at `.worktrees/<name>-<n>/` in the workspace, detached at
   `origin/main`. They come through `--settings` because Claude Code creates
   a `-w` worktree before it loads the plugins' hooks. If an issue's worktree
   is still there, kept from an earlier session, the autopilot leaves that
   issue alone and says so.

After a round with no session tab and nothing Ready on the board, it closes
its own tab. The board is read fresh in that round, after the finished
sessions' tabs are closed, and an issue the pilot already started that is
still Ready counts as Ready: its session may have stopped, so the pilot stays
on and logs `waiting, started before and unchanged since its session ended`,
instead of going quiet beside it (#159). It starts such an issue again only
when its board item changed after its session ended (the item's `updatedAt`,
already in the round's board read, against the time the pilot saw the session
end): an issue set Ready again is relaunched without toggling the pilot, and
one whose session stopped on a block nobody touched is not (#164). A round that could not read the board, on a low API budget,
does not count.

Between rounds, it compares `bin/autopilot` and `autopilot.conf` with what it
loaded at start. When one changed, it logs `autopilot code changed;
restarting` and re-executes itself (`os.execv`) with the same arguments, in
the same tab: the issues it already started are carried over, `prepare` is
not repeated, and a round in progress is never cut. A script that does not
compile is not run: the loop keeps the old code until the file changes again.
A pilot therefore picks a pulled change to `herdr/` up on its own, and one
that read a deleted file no longer dies on it.

`bin/autopilot state <repo>` prints `on` only when the loop is running in its
tab, `dead` when the tab is there and the loop exited, and `off` without the
tab. `start` closes a dead tab and opens a new one.

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

## Models

Herdr passes no model flag. Each repo's committed `.claude/settings.json`
decides its sessions' model: Opus at xhigh effort, compacting at 200k tokens,
for the workspace's orchestrator; Sonnet at medium effort for every repo's
sessions, and Sonnet for their subagents. A session started by Herdr, the
autopilot or by hand, on any machine, runs the same, whatever the user's own
settings say. Every session had run Opus with the 1M context and burned the
plan's usage (operator decisions, 2026-10-12; workspace#145). A running
session keeps its model until it ends.

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

## File viewer

[`herdr-file-viewer`](https://github.com/smarzban/herdr-file-viewer) (MIT) is
a git-aware, read-only viewer in a Herdr pane: a keyboard-driven TUI over a
repo's files, their diffs and their rendered Markdown, beside the session
that works on them. Two of its actions are bound below: one splits the
current pane (pressed again, it focuses or closes the viewer), the other
opens it in its own tab.

It is not ours, so it stays pinned. `bootstrap.sh` installs it at the tag
its `file_viewer_ref` holds, the only place the version is written:

```sh
herdr plugin install smarzban/herdr-file-viewer --ref "$file_viewer_ref" --yes
```

It runs only when `herdr plugin list` does not show the plugin at that tag,
so a second run changes nothing. Herdr never updates a plugin by itself.
To bump it, change `file_viewer_ref` in its own commit,
`chore(herdr): bump herdr-file-viewer to X.Y.Z`, and run `./bootstrap.sh`
on each machine: installing again with another `--ref` changes the version.

The viewer runs `glow` for Markdown, `delta` for diffs and `bat` for source,
from `PATH`, handing them the file on stdin, and shows plain text without
them. They come from the workspace's `mise.toml`, pinned and locked like
every tool, and `bootstrap.sh` runs `mise install` so they are there. They
resolve through mise's shims (`~/.local/share/mise/shims`), which the shell
that starts Herdr has in its `PATH` once it runs `mise activate`. They bump
as any tool does: `chore(mise): bump glow to X.Y.Z`, then `mise lock`.

Supply chain: Herdr runs the plugin's build step on install,
`scripts/fetch-or-build.sh`, which downloads a prebuilt binary from the
plugin's GitHub release and checks it against the `SHA256SUMS` of that same
release. When no binary exists for the machine, it builds from source with
`cargo build --release`. The pin fixes the version, but not what the tag
holds: it does not protect against a tag that is published again, which
would bring a new binary and its new checksums together (workspace#157).

## Setting it up, once per machine

`bootstrap.sh` links the plugin in place, so a change here reaches Herdr
with no reinstall. It also installs the file viewer and the renderers it
needs (File viewer, above). It has mise trust every config under
`~/git/github/0xc0-homelab/`, so a new worktree's `mise.toml` asks for no
`mise trust`, creates `.worktrees/`, and runs `bin/autopilot prepare` for
every org repo and for the workspace, which also trusts each in Claude Code
(Autopilot, above).

It also leaves the machine able to install the org's private packages
(`.github`'s README, Shared packages, step 5): it appends
`//npm.pkg.github.com/:_authToken=${NODE_AUTH_TOKEN}` to `~/.npmrc` when
that exact line is missing, creating the file with mode 600 and changing
nothing else in it, and it checks that gh's token has the `read:packages`
scope. When it lacks it, the script prints
`gh auth refresh -h github.com -s read:packages` and does not run it: it
opens a browser, so run it yourself. It never reads, prints or stores the
token: the line names a variable, and each install gets the token for that
command alone.

The keys go in your own Herdr `config.toml` (`prefix+a`, `prefix+shift+a`,
`prefix+f` and `prefix+shift+f` are free in the defaults), then
`prefix+shift+r` reloads it:

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

[[keys.command]]
key = "prefix+f"
type = "plugin_action"
command = "herdr-file-viewer.open-file-viewer"
description = "Open the file viewer beside this pane"

[[keys.command]]
key = "prefix+shift+f"
type = "plugin_action"
command = "herdr-file-viewer.open-file-viewer-tab"
description = "Open the file viewer in its own tab"
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
