#!/usr/bin/env bash
# Sets up this machine for the workspace's sessions (herdr/README.md), and
# gets every org repo's clone ready: the same step an autopilot takes for its
# repo when it starts.
set -euo pipefail
cd "$(dirname "$0")"

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

echo "==> herdr: link the plugin"
herdr plugin list | grep -qF "local:$PWD/herdr]" ||
  herdr plugin link "$PWD/herdr"

# The plugin's tag, the only place it is written (herdr/README.md, File viewer).
file_viewer=smarzban/herdr-file-viewer
file_viewer_ref=v1.18.0

# --yes: without a terminal, the install refuses to run without it.
echo "==> herdr: install the file viewer plugin at $file_viewer_ref"
plugins="$(herdr plugin list)"
grep -qF "github:$file_viewer@$file_viewer_ref]" <<<"$plugins" ||
  herdr plugin install "$file_viewer" --ref "$file_viewer_ref" --yes

# Each clone: cloned if missing, on an up-to-date main unless someone works
# in it, with its plugins installed for its path, and trusted by Claude Code
# (workspace#106, #115, #136).
for repo in .github claude-config infrastructure gitops vault packages offby1.cc payload artistlabco.com; do
  echo "==> $repo"
  herdr/bin/autopilot prepare "$repo"
done
echo "==> workspace: plugins and trust"
herdr/bin/autopilot prepare .
