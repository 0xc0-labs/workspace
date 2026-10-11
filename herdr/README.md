# herdr

The workspace's [Herdr](https://herdr.dev) plugin, `0xc0-workspace`: one key
opens a repo's Claude Code session in its own Herdr workspace, listed in the
sidebar with its agent's state (`docs/design.md`, How we work).

Pick a repo, and a workspace named after it opens in its directory with
`claude -n <name> "/0xc0:work-issue"`: the session takes that repo's Ready
issue of highest priority. Pick the workspace, and the orchestrator opens:
`claude -n orchestrator`. A session already open is focused, not opened twice.

## Names

A session's name is its repo's, as Herdr takes an agent's
(`[a-z][a-z0-9_-]`): dots to dashes, a leading dot dropped. The same name
goes to Herdr and to `claude -n`, so the orchestrator finds a session by it.

| Directory | Session |
|---|---|
| the workspace | `orchestrator` |
| `.github` | `github` |
| `offby1.cc` | `offby1-cc` |
| `artistlabco.com` | `artistlabco-com` |
| any other repo | its name |

## Setting it up, once per machine

Herdr reads no layout from a repo; it runs a plugin linked in place, so a
change here reaches it with no reinstall:

```sh
herdr plugin link ~/git/github/0xc0-homelab/workspace/herdr
```

The key goes in your own Herdr `config.toml` (`prefix+a` is free in the
defaults), then `prefix+shift+r` reloads it:

```toml
[[keys.command]]
key = "prefix+a"
type = "plugin_action"
command = "0xc0-workspace.open-session"
description = "Open a repo session"
```

## Files

```
herdr-plugin.toml   the action and the picker popup
bin/open-picker     the action: opens the popup
bin/pick            the popup: lists the workspace and every repo cloned in it
bin/open-session    opens or focuses one directory's session
```

`bin/open-session <dir> --dry-run` prints what it would do, touching
nothing. It needs `python3`, to read Herdr's answer.
