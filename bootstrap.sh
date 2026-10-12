#!/usr/bin/env bash
# Sets up this machine for the workspace's sessions (herdr/README.md), and
# gets every org repo's clone ready: the same step an autopilot takes for its
# repo when it starts.
set -euo pipefail
cd "$(dirname "$0")"

# A private package installs with the user's config: pnpm 12 ignores a
# credential with a variable in a repository's .npmrc (.github#124). The line
# holds the variable's name, never the token.
npmrc_line='//npm.pkg.github.com/:_authToken=${NODE_AUTH_TOKEN}'

ensure_npmrc_line() {
  local file="$HOME/.npmrc"
  [ -f "$file" ] || install -m 600 /dev/null "$file"
  grep -qxF -- "$npmrc_line" "$file" && return 0
  # Without a final newline the line would join the file's last one.
  if [ -s "$file" ] && [ -n "$(tail -c1 "$file")" ]; then echo >>"$file"; fi
  echo "$npmrc_line" >>"$file"
}

check_packages_scope() {
  local status
  status="$(gh auth status 2>&1 || true)"
  grep -qE "Token scopes:.*[' ,]read:packages[' ,]?" <<<"$status" && return 0
  echo "gh's token lacks read:packages. Run:"
  echo "  gh auth refresh -h github.com -s read:packages"
}

# Every session's worktree has its own mise.toml, which mise would ask to
# trust one by one. First, so the workspace's own tools run below.
org="$(cd .. && pwd)"
echo "==> mise: trust $org"
mise settings get trusted_config_paths | grep -qF "\"$org\"" ||
  mise settings add trusted_config_paths "$org"

echo "==> packages: ~/.npmrc and gh scope"
ensure_npmrc_line
check_packages_scope

echo "==> .worktrees"
mkdir -p .worktrees

echo "==> herdr: link the plugin"
herdr plugin list | grep -qF "local:$PWD/herdr]" ||
  herdr plugin link "$PWD/herdr"

# Each clone: cloned if missing, on an up-to-date main unless someone works
# in it, with its plugins installed for its path, and trusted by Claude Code
# (workspace#106, #115, #136).
for repo in .github claude-config infrastructure gitops vault packages offby1.cc payload artistlabco.com; do
  echo "==> $repo"
  herdr/bin/autopilot prepare "$repo"
done
echo "==> workspace: plugins and trust"
herdr/bin/autopilot prepare .
