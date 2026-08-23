#!/usr/bin/env bash
# Hashes the diff of commits that a `git push` would send to the remote (HEAD
# vs its upstream, or vs a known remote branch if no upstream is configured),
# so callers can detect whether anything new needs review since the last
# recorded push-review. Prints a sha256 hex digest to stdout and exits 0 when
# a baseline is found; exits 1 with no output when it can't determine one
# (e.g. the first push of a brand-new branch with no remote counterpart yet).
set -euo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}"

find_baseline() {
	if git rev-parse --verify -q '@{u}' >/dev/null 2>&1; then
		echo '@{u}'
		return
	fi

	branch="$(git rev-parse --abbrev-ref HEAD)"
	for ref in "origin/$branch" origin/main origin/master origin/develop; do
		if git rev-parse --verify -q "$ref" >/dev/null 2>&1; then
			echo "$ref"
			return
		fi
	done
}

baseline="$(find_baseline)"
if [ -z "$baseline" ]; then
	exit 1
fi

git diff "$baseline"..HEAD -- | sha256sum | awk '{print $1}'
