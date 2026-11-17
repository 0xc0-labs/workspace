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
  and updates each one of the org's marketplace (`@0xc0-labs`) that its
  `.claude/settings.json` enables, which Claude Code would otherwise update
  only after a session had started on the old one;
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
   alone on its line (only whitespace and Claude Code's `⏺` bullet may come
   before it; a sentence that quotes it does not count; `autopilot
   --self-test` checks this),
   and removes that session's worktree if it has no uncommitted changes and
   no commit missing from `origin`: a clean worktree whose HEAD is already in
   `origin/main` goes at once, whatever its branch, even one never pushed
   (#166). A branch GitHub deleted when its PR
   merged counts as on `origin` if that PR holds the worktree's last commit,
   since a squash merge puts its commits in `main` under other SHAs (#134).
   Otherwise it keeps the worktree and says so: uncommitted changes,
   commits only here, or a deleted branch whose PR is not merged. The
   operator looks at what is in it, saves or discards it, and removes it
   (`git worktree remove --force .worktrees/<name>-<n>` from the repo's
   clone). It never closes a session that is working or waiting on the operator;
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

   A round that starts a session updates first, once, each plugin of the
   org's marketplace that the repo enables, not only `0xc0`: a session loads
   its plugins on disk when it starts and lives for one issue, and Claude
   Code's own update reaches only the next session (#124, #221). Autopilots
   take turns at it under a lock in `~/.cache/0xc0/`, and skip the
   marketplace update when another did it under two minutes ago (#132).

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
   is still there, kept from an earlier session, the autopilot does not start
   that issue and does not count it as started: it logs the worktree's path
   when it first sees it, then every ten minutes, and starts the issue on the
   round after the worktree is gone, with no board change and no restart
   (#166).

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

Between rounds, it compares `bin/autopilot`, `autopilot.conf` and the files of
`lib/frontend/`, listed again each time so that a file added there counts as a
change, with what it loaded at start. When one changed, it logs
`autopilot code changed; restarting` and re-executes itself (`os.execv`) with
the same arguments, in the same tab: the issues it already started are
carried over, `prepare` is not repeated, and a round in progress is never cut.
Code that does not compile, the script or any file of `lib/frontend/`, is not
run: the loop keeps the old code until a watched file changes again. A pilot
therefore picks a pulled change to `herdr/` up on its own, and one that read a
deleted file no longer dies on it.

`bin/autopilot state <repo>` prints `on` only when the loop is running in its
tab, `dead` when the tab is there and the loop exited, and `off` without the
tab. `start` closes a dead tab and opens a new one.

`autopilot.conf` holds each repo's slots: two in the application repos and
in `packages`, one in the others. Picking the repo again, or closing the
`autopilot` tab, turns it off: nothing more starts, and the running
sessions finish in their tabs. To hold one issue, set it Blocked on the
board. An issue it started once is not started again until it is turned off
and on, even if its session left it Ready.

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
session already open is focused, not opened twice, in whichever front end it
lives.

### Which front end

Herdr is two products with no shared base: the terminal app (`herdr`, the
TUI), which has its own server, and the desktop app (`herdr-app`), a client of
`herdr-core` that runs every terminal it shows, driven with `hc`. What runs in
one does not show up in the other. `bin/open-session <dir>` opens the session
in the front end in use, picked by the first rule that applies:

1. The one asked for: `--frontend tui|app`, or `OXC0_HERDR_FRONTEND=tui|app`.
   The option wins over the variable.
2. The one the script is launched from: a terminal of the app has
   `HC_TERMINAL_ID`, a pane of the TUI has `HERDR_PANE_ID`. With both set, the
   TUI: its server hands its own environment to its panes, so a pane started
   from a terminal of the app has both, while the core gives its terminals no
   `HERDR*` variable.
3. Outside both: the app if its window answers (`herdr-app status` exits 0),
   otherwise the TUI.

A value that is neither `tui` nor `app`, or a front end whose programs are not
in `PATH` (`herdr` for the TUI, `hc` and `herdr-app` for the app), ends with a
message that says which.

Before opening anything, it looks for the session in the front end picked and
in every other that answers, and focuses it where it finds it, whichever
front end was picked. A front end answers when its server does, asked with a
command that does not start one that is not running: `herdr status server`
for the TUI, `hc server status` for the app's core. In the app a session is
found by the core, so it is found while the window is closed too: the script
then says the session runs and the window is not there to show it, and opens
nothing.

### In the app

A session opened by hand is a core terminal:

```sh
hc run --bg --keep --rm --no-parent --no-notify --json --name <name> --cwd <dir> \
  --label herdr.space=oxc0-<name> --label herdr.tab=oxc0-<name> \
  --label oxc0.space=<name> --label oxc0.role=session \
  -- claude -n <name> "/0xc0:work-issue"
```

The orchestrator's is `claude -n orchestrator`, with no prompt. Each part has
a reason:

- `herdr.space` and `herdr.tab` place the terminal in the app: a tab of the
  space with that id. The app makes a new space and a new tab out of ids it
  does not know, with exactly those ids, so they are ours and need no lookup.
  `oxc0.space` and `oxc0.role` are how the script finds the session
  (`hc ls --label oxc0.space=<name> --label oxc0.role=session`): a session the
  operator opened by hand lives in a space with an id of the app's own.
- `--no-parent --no-notify`: started from inside a terminal, a new terminal is
  otherwise that terminal's sub-agent, ends with it, and has notes about it
  typed into it.
- `--keep`: without it the core runs a lost program's command again, which
  here would start a new conversation by itself; with it, a shell takes its
  place.
- `--rm`: when Claude Code exits, the app closes the tab, and the space when
  it was its last tab. No shell stays behind, unlike in the TUI, where a tab
  outlives its session, and nothing finished is left in the core.

The window, when it answers, only names and shows it: the space and the tab
are renamed `<name>` (retried for a few seconds, since the app shows a new
terminal a moment after `hc run` returns), and the session is focused. When it
does not answer, the session still starts, with its space and tab unnamed, and
the script says the window was not there. For the script to find a session
the operator opened without it, the operator adopts it with
`hc label <terminal> oxc0.space=<name> oxc0.role=session`; the script never
does it.

Nothing here types into a terminal or reads its screen: no `hc send`,
`hc keys`, `hc attach`, `hc get` or `hc read`, and nothing with `--force`.

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
From Herdr 0.9.4, `herdr plugin update` does, on request only, at the ref
recorded when the plugin was installed. For the file viewer that is the tag
in `file_viewer_ref`: the command fetches it again and, if it now holds
another commit than the installed one, installs that commit and runs the
build step again; otherwise it says the plugin is up to date. It takes no
`--ref`, so it cannot move the plugin to another tag, and fetching the same
tag a second time is the case workspace#157 is about (Supply chain, below).
It never updates a linked plugin, so it does not touch `0xc0-workspace`.
To bump the file viewer, change `file_viewer_ref` in its own commit,
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
(`.github`'s README, Shared packages, step 5): it keeps any
`//npm.pkg.github.com/:_authToken=` line `~/.npmrc` already holds, and
changes nothing in the file. With none, it writes nothing and prints how to
add a read-only token: a classic token with only `read:packages`, entered
with `read -s` and written into `~/.npmrc` (mode 600). It never reads,
prints or stores the token, and gh's token is not used for installs.

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

## Upgrading Herdr

Herdr is the operator's own install, not the workspace's: a Homebrew one on
the operator's machine. Four steps, and only the third ends anything:

1. The binary first, with whatever installed it: `brew upgrade herdr`
   (Herdr's own `herdr update` is disabled for a Homebrew install). No
   session ends. The server that is running keeps the version it started
   with, and the new binary's commands talk to it while both speak the same
   protocol version. When they do not, a command that talks to the server
   fails with `protocol_mismatch` until step 3.
2. Check what can be checked then, touching nothing: `herdr --version`;
   `herdr status`, which shows both versions and whether the server's
   protocol is compatible with the client's; `herdr plugin list`, which
   still lists `0xc0-workspace` and the file viewer at its tag;
   `bin/autopilot --self-test`; `bin/open-session <dir> --dry-run`; and
   `bin/autopilot state <repo>`.
3. The server runs the new version only once it is started again.
   `herdr server stop` stops it, and that ends every pane's process: the
   orchestrator, every repo session and every autopilot. So it is done when
   nothing is working, never in passing, from a terminal outside Herdr.
   Running `herdr` starts it again.
4. Afterwards, `herdr plugin list` again, and `bin/autopilot start <repo>`
   for each repo whose autopilot was on: it does not come back by itself.
   Herdr restores the workspaces and their tabs, not their processes, so an
   autopilot's tab may be there with no loop in it; `start` replaces it
   (Autopilot, above).

## Files

```
herdr-plugin.toml         the actions and their popups
autopilot.conf            each repo's slots
bin/open-picker           an action: opens a popup
bin/pick                  the popups: the workspace and every repo cloned in it
bin/open-session          opens or focuses one directory's session, in the
                          front end in use
bin/autopilot             the autopilot: its loop, and starting or toggling it
lib/frontend/__init__.py  what the two scripts ask of Herdr, the rule that
                          picks the front end, and the loading of the backend
                          that does it
lib/frontend/tui.py       the backend for Herdr's terminal app: every call to
                          the `herdr` binary the two scripts make
lib/frontend/app.py       the backend for Herdr's desktop app: every call to
                          `hc` and `herdr-app` the two scripts make
```

The two scripts never run `herdr`, `hc` or `herdr-app`: they ask
`lib/frontend/`, in terms of spaces, tabs and sessions, and its backend
translates them: `tui` into `herdr`'s workspaces, tabs and agents, `app` into
the core's terminals and the window's spaces and tabs. `open-session` takes
the backend by the rule in Opening a session by hand. The autopilot takes
`tui` whichever front end the rule would pick, and `app` has only what
`open-session` needs: the autopilot's operations come next
(0xc0-labs/workspace#231). Asking a backend for an operation it lacks fails
with a message.

`bin/open-session <dir> --dry-run`, with either `--frontend`, prints what it
would do, touching nothing. `bin/autopilot --self-test` checks the rule, and
the app backend reading answers of `hc` and `herdr-app` recorded from the
real ones, with no Herdr running; it also says what each backend has. Both
scripts need `python3`, from the OS: they are written in it, with its standard
library alone. The autopilot runs `gh` through mise, from the workspace's
`mise.toml`.
