# herdr

The workspace's [Herdr](https://herdr.dev) integration: a plugin for its
terminal app and a mod for its desktop app, both called `0xc0-workspace`. One
key opens a repo's Claude Code session in its own Herdr workspace, or the
orchestrator. Another turns a repo's autopilot on or off: the autopilot
works the repo's Ready issues, one fresh session per issue, each in its own
tab and worktree, and turns itself off when nothing is left
(`docs/design/how-we-work.md`). The orchestrator starts it with
`bin/autopilot start <repo>` after it sets issues Ready. Both run in Herdr's
terminal app (the TUI) or in its desktop app, whichever is in use (Which front
end, below). In the TUI the keys are two plugin actions, each opening a
popup; in the app they are one popup with both (The picker in the app, below).

Herdr also runs one third-party plugin the workspace installs, the file
viewer (File viewer, below).

## Autopilot

`bin/autopilot start <repo>`, or picking a repo from the key, gives the
repo's Herdr workspace an `autopilot` tab running `bin/autopilot run <repo>`,
which logs a line for everything it does. In the desktop app that tab is a
terminal of the app's core (The autopilot in the app, below). It first gets
the repo's clone ready, as `bin/autopilot prepare <repo>` does:

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
tab. `start` closes a dead tab and opens a new one. It looks in every front end
that answers, not only the one in use: `on` anywhere is `on`, and `start` then
starts nothing, since a repo never has two autopilots (Where it runs, below).

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
remove and start, changing nothing; with the app, the `hc` commands it would
run to start a session and to end one, and the window's commands that would
name them. It still reads the board once, and the sessions, and the answer of
`hc read` for a session at rest, whose text goes to the search for the last
line and nowhere else.

### Where it runs

The front end is the one `open-session` takes, by the same rule (Which front
end, below): `--frontend tui|app`, else `OXC0_HERDR_FRONTEND`, else the one the
script runs in, else the app if its window answers. `run`, `start`, `toggle`
and `state` take the option. A pilot's loop is told its front end when it is
started, so the rule does not decide it again where it runs: in the app
through `env OXC0_HERDR_FRONTEND=app` in its terminal's command, in the TUI
through `--frontend tui` in the command typed into its pane. Its sessions open
where the loop runs, and it restarts itself with the same arguments.

`start`, `toggle` and `state` look for the pilot in the front end picked and
in every other that answers (the TUI's server, the app's core) before acting,
and never start a server that is not running to ask: no `hc` command is run
for a front end that was not picked until its core's socket accepted a
connection. A pilot found in another front end than the one picked is
reported there, `gitops: autopilot already on (in the app)`, or turned off
there by `toggle`, and `start` starts none while one is on anywhere. A dead
one in any front end is closed, and `start` starts a new one in the front end
picked. With only the TUI in use nothing changes: the same calls to `herdr`,
the same lines.

### The autopilot in the app

The pilot's loop, and each session it starts, are terminals of the app's core,
found by labels of ours (`oxc0.space=<name>`, `oxc0.role`), as the sessions
opened by hand are (In the app, below):

| Terminal | `--name` | `herdr.tab` | Labels of ours |
|---|---|---|---|
| a repo's session, opened by hand | `<name>` | `oxc0-<name>` | `oxc0.space=<name>`, `oxc0.role=session` |
| a pilot's session | `<name>-<n>` | `oxc0-<name>-<n>` | `oxc0.space=<name>`, `oxc0.role=worker`, `oxc0.issue=<n>` |
| a pilot's loop | `<name>-autopilot` | `oxc0-<name>-autopilot` | `oxc0.space=<name>`, `oxc0.role=autopilot` |

Everything of one repo carries `herdr.space=oxc0-<name>`, which puts it in one
space of the app. When the window answers (`herdr-app status` exits 0), the
space is named `<name>` and the tabs `<name>-<n>` and `autopilot`, as in the
TUI; when it does not, they still start, with the space and the tab unnamed
and nothing else different. Each is made in the background, with no parent
and no notes (`--no-parent --no-notify`), so the focus does not move:

```sh
hc run --bg --keep --no-parent --no-notify --json --name <name>-<n> --cwd <repo's directory> \
  --label herdr.space=oxc0-<name> --label herdr.tab=oxc0-<name>-<n> \
  --label oxc0.space=<name> --label oxc0.role=worker --label oxc0.issue=<n> \
  -- env OXC0_AUTOPILOT=1 claude --permission-mode auto --settings <workspace>/.worktrees/.hooks.json \
     -n <name>-<n> -w <name>-<n> "/0xc0:work-issue <repo>#<n>"

hc run --bg --no-parent --no-notify --json --name <name>-autopilot --cwd <cwd> \
  --label herdr.space=oxc0-<name> --label herdr.tab=oxc0-<name>-autopilot \
  --label oxc0.space=<name> --label oxc0.role=autopilot \
  -- env OXC0_HERDR_FRONTEND=app <workspace>/herdr/bin/autopilot run <repo's directory>
```

The arguments run as given, with no shell in between, and the core gives a
terminal its own environment, not the caller's: that is why the variables go
through `env`. A session has `--keep`, so that the core never runs its command
again by itself, which would start a new conversation; a loop has none, since a
loop run again reads the board and the sessions and goes on (`hc get` reads
`"keep": true` for it all the same: what a restart of the core does to them,
below). Neither has
`--rm`: what is left of a terminal that ended is what the pilot reads.

A session's state comes from the core, from `hc ls --all` filtered by the
labels, and is read at every round:

| The row says | The session is |
|---|---|
| `state: "finished"` | ended: its program left (`reason` `exited` or `killed`, with `exit_code`): handled as "its session exited" |
| `live`, no `status` yet | starting: busy, unless a shell took its program's place (below): then ended |
| `live`, `turn` 0, any `status` | busy. Claude Code reports `idle` once before it takes its prompt |
| `live`, `turn` 1 or more, `status` `idle` or `done` | at rest: its last lines are read, and the session is closed if one is its last line |
| `live`, anything else | busy. A session stopped at a question of Claude Code's (`blocked`, as at "trust this folder") is busy: the operator's to answer, never the pilot's |

The first row's exception is the one `hc ls` cannot show. `hc run --help` says
`--keep` replaces lost programs with a shell in place, and `hc schema` says
the new shell never reports; its row is `live` and stays with no `status`,
like a session still starting. `hc ls` does not say what runs in front, but
`hc get` does, in `foreground`: for a session that reports nothing, the pilot
asks `hc get` and takes the session as ended when the command line in front
is neither Claude Code's, which carries the name the session was given
(`-n <name>`), nor `env`, which is it for a moment before it becomes it. That
is one of the two places the pilot runs `hc get`, the other being a live loop's
terminal (below): it drops the answer's `screen`, the terminal's whole text, as
it reads it, and a call that fails never says what it wrote, only the `error`
it answered as JSON or else its exit status, as for `hc read`. No test could
reach a shell in a session's place, because it takes restarting the core: the
self-test holds a stand-in for that answer, built from `hc schema`.

A session ends in this order: its screen is read (`hc read <t> --json --lines
80`, whose `text` goes to the search for the last line and nowhere else: a
killed terminal answers an incomplete screen), then `hc kill <t>`, `hc wait <t>
--timeout 10 --json`, which ends when the terminal does and never waits for ever,
and `hc rm <t>`, which takes a finished terminal only. The app closes the tab
when the terminal ends. A session whose program was gone is killed and
removed all the same, and one already finished is removed. No finished
session stays in the core. The pilot never types into a terminal: no
`hc send`, `hc keys` or `hc attach`, and nothing with `--force`.

A pilot's state, from `hc ls --all` filtered by `oxc0.role=autopilot`:

| The core has | `state` prints | What `start` and `toggle` do first |
|---|---|---|
| a live terminal with the loop in front, or `env`, or nothing yet | `on` | `toggle`: `hc kill`, then `hc rm` |
| a live terminal with anything else in front, a shell included | `dead` | `hc kill`, `hc wait`, then `hc rm` it |
| none live, a finished one that exited with 0 | `off` | `hc rm` it |
| none live, a finished one with another exit code, or none | `dead` | `hc rm` it |
| none | `off` | |

`live` says a program runs in the loop's terminal, not which: a loop that was
lost may be a shell in its place, live with no loop. So for a live terminal
`state` asks `hc get`, as it does for a session that reports nothing, and reads
`foreground.argv`, as recorded from a running loop (2026-11-17, `hc` 0.1.21): the
interpreter, then `<workspace>/herdr/bin/autopilot`, then `run`, then the
repo's directory. The loop is the command line whose second word ends in
`herdr/bin/autopilot` and whose third is `run`: the path is not compared whole,
so a loop started from another checkout of the workspace is the loop. `env` in
front is the loop a moment after `start`, before it is, and a terminal with no
`foreground` yet is the same moment. Anything else, a shell or another
program, is not the loop: `dead`, so that `start` closes the terminal and
starts a new loop, as for one that finished. The call is one `hc get` per live
terminal, its `screen` dropped.

A loop that ends because nothing is left exits 0: its tab closes by itself,
and the next `state`, `start` or `toggle` removes what is left of it. A loop
that died leaves its last lines and exit code in the core until then, so read
them first:

```sh
hc read <name>-autopilot --lines 80
```

`start` on a dead pilot then removes it and starts a new loop, printing
`<repo>: autopilot was dead; restarting`.

What a restart of the core does to them, as far as `hc`'s help and `hc schema`
say, since it ends the operator's sessions and none was tried:

- `hc server restart`, after an update: "programs keep running" and the next
  core adopts them. The pilot and its sessions go on.
- `hc server stop`: "stops the core and its programs. Kept terminals remain
  pending and get new shells when the core next starts". The sessions, which
  are kept, come back as a shell each, `live` with nothing in front and
  nothing reported: the pilot ends them as above. What the core does to the
  loop is not known: started without `--keep`, it reads `"keep": true` in `hc
  get` (observed 2026-11-17, `hc` 0.1.21), and `hc run` has no flag that turns
  it off. It may come back as a shell like a session, `live` with no loop, or
  finish with an exit code. `state` does not depend on which: it tells a loop
  from what took its place by what runs in front (above), and says `dead` or
  `off` by the exit code for a finished one. `start` is what brings it back, as
  after the TUI's server stops. A worktree with unpushed work stays.
- The core or a program lost: a kept terminal is replaced by a shell after a
  grace delay, one that is not kept finishes with a `reason` (`holder_lost`,
  `signaled`), a session a shell again. A loop reads as kept, so which of the
  two it gets was not seen. Either way `state` does not say `on`.

Untried: what the core does to a loop when it stops or loses it. Stopping the
core is the operator's, and it ends every session, so it was not tried.

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
in the front end in use, and `bin/autopilot` runs its loop and its sessions in
it (Autopilot, above), picked by the first rule that applies:

1. The one asked for: `--frontend tui|app`, or `OXC0_HERDR_FRONTEND=tui|app`.
   The option wins over the variable.
2. The one the script is launched from: a terminal of the app has
   `HC_TERMINAL_ID`; whatever the TUI starts has `HERDR_ENV=1`, a pane as much
   as a plugin's popup. `HERDR_PANE_ID` does not tell: the TUI starts a popup
   without it, and `bin/pick` runs `open-session` from one. With both set, the
   TUI: its server hands its own environment to what it starts, so one
   started from a terminal of the app has both, while the core gives its
   terminals no `HERDR*` variable.
3. Outside both: the app if its window answers (`herdr-app status` exits 0),
   otherwise the TUI.

A value that is neither `tui` nor `app`, or a front end whose programs are not
in `PATH` (`herdr` for the TUI, `hc` and `herdr-app` for the app), ends with a
message that says which.

Before opening anything, it looks for the session in the front end picked and
in every other that answers, and focuses it where it finds it, whichever
front end was picked. A front end answers when its server does, and the
question never starts a server that is not running:

- TUI: `herdr status server` reports the server's status, running or not.
- The app's window, which the rule's third row and focusing use:
  `herdr-app status` exits 0.
- The app's core, which looking a session up uses: whether its socket accepts
  a connection, closed at once, with no `hc` command. `hc server status` is
  not that question: on macOS and Linux it starts a core that is not running,
  and so does every `hc` command that asks. The socket is where `hc` looks for
  it (`herdr-core` 0.1.21): `HC_SOCKET` when set; else the top-level `socket`
  key of `${XDG_CONFIG_HOME:-~/.config}/herdr-core/config.toml`; else
  `<run>/<session>.sock`, with `<session>` the `HC_SESSION` or `default`, and
  `<run>` the `$XDG_RUNTIME_DIR/herdr-core`, or `/run/user/<uid>/herdr-core`
  when that is a directory, or else
  `${XDG_STATE_HOME:-~/.local/state}/herdr-core/<session>`. A socket file
  nobody listens on refuses the connection: the core is not running.

In the app a session is found by the core, so it is found while the window is
closed too: the script then says the session runs and the window is not there
to show it, and opens nothing.

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

Opening a session types into no terminal and reads no screen: no `hc send`,
`hc keys`, `hc attach`, `hc get` or `hc read`, and nothing with `--force`. The
autopilot reads a session's screen only as The autopilot in the app, above,
says.

## The picker in the app

The desktop app has no plugins like the TUI's: it loads mods, a folder with a
`main.js` and a `mod.json`, and a mod is trusted code with no isolation, as the
TUI's plugin linked from this repo already is. `mods/0xc0-workspace/` is ours.
In the TUI a popup is a script that reads a number, so the two keys are two
popups. In the app it is one popup with a list and two actions, and one key to
bind.

It lists the workspace and every repo cloned in it, filtered by name as you
type, and fills in each repo's autopilot, `on`, `off` or `dead`, once the list
shows:

| Key | What it runs | Then |
|---|---|---|
| Enter, or a click | `bin/open-session <dir> --frontend app` for the entry marked | the popup closes; if the script fails, it stays and shows what it printed |
| Ctrl+T | `bin/autopilot toggle <dir> --frontend app`, then `bin/autopilot state <dir> --frontend app` | the line the toggle printed, and the entry's new state |
| ↑ and ↓ | | mark another entry |
| Esc | | closes the popup |

The mod has no logic about sessions or pilots of its own, and no path written
by hand. It runs `bin/pick --list` for the list, `bin/pick --autopilot --list
--frontend app` for the states, and the two scripts above, and shows what they
print, their errors included. `bin/pick --list` prints the list the TUI's
popups show, one entry a line, tab-separated: the directory and the label.
With `--autopilot` each line has the state as a third field. The workspace's
own entry has no autopilot: Ctrl+T on it shows what the script says, that it is
not a repo of the workspace. Ctrl+T does nothing while the states are being
read, so that a late answer does not overwrite the new one. The mod's `exec`,
which runs the scripts, takes no environment of its own, so the front end goes
as the option `--frontend app` and not as `OXC0_HERDR_FRONTEND` (Which front
end, above). The environment it has is the login one, with no mise: the scripts
run with the OS's `bash` and `python3` (3.9 on the operator's machine), so
nothing in them may ask for a newer Python, and
`/usr/bin/python3 bin/autopilot --self-test` checks it.

How the mod finds the workspace: a mod cannot ask where it is. The app holds
it as a link, `<app home>/mods/0xc0-workspace`, to `herdr/mods/0xc0-workspace`
here; the mod resolves that link physically (`pwd -P`) and takes the folder
three levels up. A copy of the mod instead of a link, or a link to a folder
that is not in this repo, does not load: the popup says it is not a link to
`herdr/mods/0xc0-workspace` of the workspace.

Installing it: `./bootstrap.sh` links it, once per machine. A link needs no
refresh: each open of the popup reads the files as they are then, so a pull is
enough. A change made while the popup is shown is not seen until the next open.
Without `bootstrap.sh`:

```sh
ln -s "$PWD/herdr/mods/0xc0-workspace" ~/.config/herdr-app/mods/0xc0-workspace
```

The key is the operator's. Nothing here writes `keys.json`, `settings.json` or
a layout, `bootstrap.sh` and the mod included. To bind the popup, add this line
to the `global` section of `~/.config/herdr-app/keys.json`
(`cmd-shift-a` is free in the default `keys.json` of 0.1.16; the same command
opens the popup and, called again, closes it):

```json
"cmd-shift-a": "mod.open:0xc0-workspace"
```

`herdr-app commands` lists `mod.open`. It works from the terminal too, which is
how to open the popup without a key: `herdr-app do mod.open --name
0xc0-workspace`.

What a session and a pilot look like there is in In the app and The autopilot
in the app, above: a session is a terminal of the core, shown as a tab of a
space of the app, both named after the repo; a pilot's loop is a terminal named
`<name>-autopilot`, shown as the `autopilot` tab of that space, and each session
it starts a `<name>-<n>` tab. The popup only has them started, found and ended,
through the scripts.

What the app keeps of the mod, once it has seen it:

- its name in `~/.config/herdr-app/seen.json`, and an empty folder
  `~/.config/herdr-app/data/0xc0-workspace/`;
- while the app's telemetry is on, its name in the day's list of mods
  (`telemetry/today.json`). The setting is the operator's, in `settings.json`:
  nothing here changes it;
- in the mod's own folder, when it loads it or `herdr-app check` does,
  `jsconfig.json` and `gpui-kit.d.ts` (820 KB). They are the app's, and the
  root `.gitignore` keeps them out of git.

`herdr-app check herdr/mods/0xc0-workspace` loads the mod and renders it once.
The mod starts nothing during a check (`checking()`): its scripts run only in a
live window. `herdr-app status` lists the mod under `overlays` once it is
opened, with its `errors`, empty when it is fine.

Checked on 2026-11-17 with `herdr-app` 0.1.16 and `hc` 0.1.21, with throwaway
mods in the live window: a linked mod loads, a name that starts with a digit
works, and each open reads the files as they are then. The app and its core are
0.1.x and update themselves, so an update can break what this relies on, with
no change here:

- the mod's own API, the `herdr` and `gpui-kit` modules, or `mod.json`: the mod
  stops loading, or draws wrong. `herdr-app check herdr/mods/0xc0-workspace`
  says so with the exact error, and `herdr-app status` lists it under the
  mod's `errors`. The popup is the only thing that breaks;
- the commands the backend uses (`hc`, `herdr-app do`): `open-session` and the
  autopilot stop working in the app, wherever they are asked from.
  `bin/autopilot state <repo> --frontend app` asks the real core and changes
  nothing; `bin/autopilot --self-test` only says the backend still reads the
  answers recorded from 0.1.x, not that the programs still give them.

The way back is the TUI, and nothing there depends on the app: its plugin and
its two keys stay as they are, and `bootstrap.sh` keeps setting them up.
`--frontend tui`, or `OXC0_HERDR_FRONTEND=tui`, on `open-session` and
`autopilot` asks for the TUI from any terminal, and an autopilot already
running in the app is found and turned off there by `toggle` (Where it runs,
above). To stop loading the mod, remove its link, `rm
~/.config/herdr-app/mods/0xc0-workspace`: the link only, not the folder it
points to.

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
| any other repo | its name | `gitops-19` |

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

`bootstrap.sh` sets up each Herdr front end that is installed, and says which
it skipped. With the TUI (`herdr` in `PATH`) it links the plugin in place, so a
change here reaches Herdr with no reinstall, and installs the file viewer. With
the desktop app (`herdr-app` in `PATH`) it links the mod into
`~/.config/herdr-app/mods/` (The picker in the app, above): a link that already
leads here stays, anything else it finds at that path it refuses to replace and
fails, and so it does when the app's `mods/` folder is not there yet, since the
app has to start once to make it. It fails too when neither front end is
installed. It writes no `keys.json`, `settings.json` or layout of either. It
also installs the renderers the file viewer needs (File viewer, above). It has
mise trust every config under
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

The desktop app's one key is a line in the `global` section of its own
`keys.json`, which the operator edits: The picker in the app, above, has it.

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
herdr-plugin.toml         the TUI's actions and their popups
autopilot.conf            each repo's slots
bin/open-picker           an action: opens a popup
bin/pick                  the TUI's popups: the workspace and every repo cloned
                          in it; with --list, the list they show, for the app's
                          mod to read
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
mods/0xc0-workspace/      the app's mod, linked into its folder by
                          bootstrap.sh: main.js and mod.json, one popup with
                          both keys (The picker in the app)
```

The two scripts never run `herdr`, `hc` or `herdr-app`: they ask
`lib/frontend/`, in terms of spaces, tabs and sessions, and its backend
translates them: `tui` into `herdr`'s workspaces, tabs and agents, `app` into
the core's terminals and the window's spaces and tabs. Both scripts take the
backend by the rule in Opening a session by hand, and each backend has every
operation they use. Asking a backend for an operation it lacks fails with a
message.

`bin/open-session <dir> --dry-run`, with either `--frontend`, prints what it
would do, touching nothing, and so does `bin/autopilot run <repo> --dry-run`.
`bin/autopilot --self-test` checks the rule, where the app's core socket is
looked for and whether it answers (on a temporary socket), the app backend
reading the answers of `hc` and `herdr-app`, and the autopilot's flow of
`start`, `toggle` and `state` over stand-in backends, with no Herdr running; it
also says what each backend has. Of those answers, the rows of `hc ls`, the
answers of `hc run`, `hc rm`, `hc wait` and `hc read` (`{"complete": true,
"how": "stitched", "text": …}`), the fields of `hc get` (including
`foreground`, a running loop's too, 0xc0-labs/workspace#235) and `herdr-app
do`'s `{"ok": true}` were recorded from the real programs
(0xc0-labs/workspace#226, #231); the last line of a session is found in a
recorded answer of `hc read`. The others are stand-ins of the documented
shape, from `hc schema` and each command's help: the `hc get` of a session or
a loop left as a shell, which takes restarting the core, the answer of `hc
kill`, which the backend does not read, the window's list of commands and the
errors. It also checks that a failed `hc get` or `hc read` says only its JSON
`error` or its exit status, and that a live loop's terminal is `on` with the
loop, `env` or nothing in front and `dead` with anything else. Both scripts
need `python3`, from the OS: they are written in it, with its standard library
alone. The autopilot runs `gh` through mise, from the workspace's `mise.toml`.
