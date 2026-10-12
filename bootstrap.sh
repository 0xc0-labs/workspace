#!/usr/bin/env bash
# Sets up this machine for the workspace's sessions (herdr/README.md), and
# gets every org repo's clone ready: the same step an autopilot takes for its
# repo when it starts.
set -euo pipefail
cd "$(dirname "$0")"

# Every session's worktree has its own mise.toml, which mise would ask to
# trust one by one. First, so the workspace's own tools run below.
org="$(cd .. && pwd)"
echo "==> mise: trust $org"
mise settings get trusted_config_paths | grep -qF "\"$org\"" ||
  mise settings add trusted_config_paths "$org"

echo "==> .worktrees"
mkdir -p .worktrees

echo "==> herdr: link the plugin"
herdr plugin list | grep -qF "local:$PWD/herdr]" ||
  herdr plugin link "$PWD/herdr"

# Each clone: cloned if missing, on an up-to-date main unless someone works
# in it, with its plugins installed for its path (workspace#106, #115).
for repo in .github claude-config infrastructure gitops vault offby1.cc payload artistlabco.com; do
  echo "==> $repo"
  herdr/bin/autopilot prepare "$repo"
done
echo "==> workspace: plugins"
herdr/bin/autopilot prepare .
