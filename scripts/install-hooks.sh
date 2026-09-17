#!/usr/bin/env bash
# Install this repo's local git hooks.
#
#   bash scripts/install-hooks.sh
#
# Hooks live in .git/hooks/, which git does not version-control, so every
# clone has to install them once. The credential scan is the important one:
# it blocks a commit whose staged diff contains a real-looking API key.
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
hooks_dir="$repo_root/.git/hooks"
mkdir -p "$hooks_dir"

install -m 0755 "$repo_root/scripts/pre-commit-credential-scan.sh" "$hooks_dir/pre-commit"
echo "installed: .git/hooks/pre-commit  (credential scan)"

echo
echo "Done. To verify, stage a line containing a RunPod-style key"
echo "(prefix 'rpa_' followed by 30+ characters) and attempt a commit —"
echo "the hook should refuse it."
echo
echo "Bypass (use deliberately): SECRETS_OK=1 git commit ..."
