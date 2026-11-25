#!/usr/bin/env bash
# Sets up this machine for the workspace's sessions (herdr/README.md), and
# gets every org repo's clone ready: the same step an autopilot takes for its
# repo when it starts.
set -euo pipefail
cd "$(dirname "$0")"

# Herdr is two products with no shared base (herdr/README.md, Which front
# end): each is set up where it is installed, and one of them is enough.
tui=false
app=false
command -v herdr >/dev/null && tui=true
command -v herdr-app >/dev/null && app=true
if ! $tui && ! $app; then
  echo "Neither Herdr front end is installed: herdr (the terminal app) and herdr-app (the desktop app) are not in PATH. Install one, then run this again." >&2
  exit 1
fi

# A private package installs with the user's config: pnpm 12 ignores a
# credential with a variable in a repository's .npmrc (.github#124). Any
# token line already in ~/.npmrc stays as it is: a later line with a
# variable would override it.
check_packages_token() {
  grep -qs '^//npm.pkg.github.com/:_authToken=' "$HOME/.npmrc" && return 0
  cat <<'MSG'
~/.npmrc has no token for GitHub Packages. Add a classic token with only
read:packages (.github's README, Shared packages, step 5):
  read -s "t?token: "; echo
  touch ~/.npmrc; chmod 600 ~/.npmrc
  echo '//npm.pkg.github.com/:_authToken=TOKEN' | sed "s/TOKEN/$t/" >>~/.npmrc
  unset t
MSG
}

# The desktop app reads a mod from a folder of its own, one per name. A link
# there to the mod in this repo needs no copy and no reinstall: the app reads
# the files as they are at each open (herdr/README.md, The picker in the app).
# A link that already leads here stays; anything else at that path is not ours
# to replace. Nothing else of the app's folder is written: no setting, key
# binding or layout.
link_app_mod() {
  local mods="${HERDR_APP_HOME:-$HOME/.config/herdr-app}/mods"
  local link="$mods/0xc0-workspace" target="$PWD/herdr/mods/0xc0-workspace"
  if [ ! -d "$mods" ]; then
    echo "$mods does not exist: start Herdr's desktop app once, then run this again." >&2
    return 1
  fi
  if [ -e "$link" ] || [ -L "$link" ]; then
    if [ -L "$link" ] && [ "$(cd "$link" 2>/dev/null && pwd -P)" = "$(cd "$target" && pwd -P)" ]; then
      echo "$link already leads to $target"
      return 0
    fi
    echo "$link is not a link to $target: move it away, then run this again." >&2
    return 1
  fi
  ln -s "$target" "$link"
  echo "linked $link to $target"
}

# Every session's worktree has its own mise.toml, which mise would ask to
# trust one by one. First, so the workspace's own tools run below.
org="$(cd .. && pwd)"
echo "==> mise: trust $org"
mise settings get trusted_config_paths | grep -qF "\"$org\"" ||
  mise settings add trusted_config_paths "$org"

echo "==> mise: install the workspace's tools"
mise install

echo "==> packages: ~/.npmrc token"
check_packages_token

echo "==> .worktrees"
mkdir -p .worktrees

# The plugin's tag, the only place it is written (herdr/README.md, File viewer).
file_viewer=smarzban/herdr-file-viewer
file_viewer_ref=v1.18.0

if $tui; then
  echo "==> herdr: link the plugin"
  # Captured, not piped: grep -q exits at the first match and the list then
  # ends with 141 under pipefail (#241).
  plugins="$(herdr plugin list)"
  grep -qF "local:$PWD/herdr]" <<<"$plugins" ||
    herdr plugin link "$PWD/herdr"

  # --yes: without a terminal, the install refuses to run without it.
  echo "==> herdr: install the file viewer plugin at $file_viewer_ref"
  plugins="$(herdr plugin list)"
  grep -qF "github:$file_viewer@$file_viewer_ref]" <<<"$plugins" ||
    herdr plugin install "$file_viewer" --ref "$file_viewer_ref" --yes
else
  echo "==> herdr: skipped, the terminal app is not installed (herdr is not in PATH): no plugin, no file viewer"
fi

if $app; then
  echo "==> herdr-app: link the mod"
  link_app_mod
else
  echo "==> herdr-app: skipped, the desktop app is not installed (herdr-app is not in PATH): no mod"
fi

# Each clone: cloned if missing, on an up-to-date main unless someone works
# in it, with its plugins installed for its path, and trusted by Claude Code
# (workspace#106, #115, #136).
for repo in .github claude-config infrastructure gitops vault packages offby1.cc artistlabco.com matchmark matchmark-config matchmark-playground; do
  echo "==> $repo"
  herdr/bin/autopilot prepare "$repo"
done
echo "==> workspace: plugins and trust"
herdr/bin/autopilot prepare .
