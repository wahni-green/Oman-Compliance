#!/usr/bin/env bash
# Run this after independently reviewing the commits about to be pushed (e.g.
# via the `code-review` skill or an Agent-tool subagent). Records their diff
# hash so the PreToolUse push-gate hook (check-before-push.sh) allows the next
# `git push` to proceed. For a plain push of the current branch to its usual
# remote, run with no args. For anything else, pass the exact
# $1=remote $2=local_ref $3=remote_ref check-before-push.sh's denial reason
# gave you — otherwise this records a marker for a different target than the
# one you're about to push, and the gate won't recognize it as reviewed.
set -euo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}"

mkdir -p .claude
if ! "$(dirname "$0")/diff-hash.sh" "$@" >.claude/.last-reviewed-diff-hash; then
	rm -f .claude/.last-reviewed-diff-hash
	echo "No baseline to compare against (e.g. no matching remote branch yet) — nothing to record."
	exit 0
fi
echo "Recorded review marker for current diff: $(cat .claude/.last-reviewed-diff-hash)"
