#!/usr/bin/env bash
# Clones (or updates) the org repos inside the workspace, and sets up what the
# sessions need on this machine (herdr/README.md).
set -euo pipefail
cd "$(dirname "$0")"

ORG=0xc0-labs

clone() {  # $1 = repo name, $2 = local directory
  if [ -d "$2/.git" ]; then
    echo "==> $2: pull"
    git -C "$2" pull --ff-only
  else
    echo "==> $2: clone"
    gh repo clone "$ORG/$1" "$2"
  fi
}

clone .github        .github
clone claude-config  claude-config
clone infrastructure infrastructure
clone gitops         gitops
clone vault          vault
clone offby1.cc      offby1.cc
clone payload        payload
clone artistlabco.com artistlabco.com

# Claude Code loads a repo's enabled plugins only once they are installed
# for its path; a session in one of its worktrees uses that record
# (workspace#106). Local scope leaves the tracked settings untouched.
installed="$(claude plugin list --json)"
for dir in . .github */; do
  dir="$(cd "$dir" && pwd)"
  [ -f "$dir/.claude/settings.json" ] || continue
  for plugin in $(jq -r '.enabledPlugins // {} | to_entries[] | select(.value) | .key' "$dir/.claude/settings.json"); do
    jq -e --arg id "$plugin" --arg path "$dir" \
      'any(.[]; .id == $id and (.scope == "user" or .projectPath == $path))' \
      <<<"$installed" >/dev/null && continue
    echo "==> $(basename "$dir"): install $plugin"
    (cd "$dir" && claude plugin install "$plugin" --scope local)
  done
done

echo "==> .worktrees"
mkdir -p .worktrees

# Every session's worktree has its own mise.toml, which mise would ask to
# trust one by one.
org="$(cd .. && pwd)"
echo "==> mise: trust $org"
mise settings get trusted_config_paths | grep -qF "\"$org\"" ||
  mise settings add trusted_config_paths "$org"

echo "==> herdr: link the plugin"
herdr plugin list | grep -qF "local:$PWD/herdr]" ||
  herdr plugin link "$PWD/herdr"
