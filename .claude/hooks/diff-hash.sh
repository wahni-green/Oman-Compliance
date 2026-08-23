#!/usr/bin/env bash
# Hashes the diff of commits that a `git push` would send to the remote.
# Optional args ($1 remote, $2 local ref, $3 remote ref) name the actual push
# target (parsed by check-before-push.sh from the real command) and take
# priority over the generic upstream/current-branch guesses below — without
# them, a push to an explicit `<remote> <refspec>` other than the current
# branch's own upstream would be checked against the wrong commit range.
# Prints a sha256 hex digest to stdout and exits 0 when a baseline is found;
# exits 1 with no output when it can't determine one (e.g. the first push of
# a brand-new branch/remote with no local remote-tracking ref yet).
set -euo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}"

remote="${1:-}"
local_ref="${2:-HEAD}"
remote_ref="${3:-}"

find_baseline() {
	if [ -n "$remote" ] && [ -n "$remote_ref" ] && git rev-parse --verify -q "$remote/$remote_ref" >/dev/null 2>&1; then
		echo "$remote/$remote_ref"
		return
	fi

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

git diff "$baseline".."$local_ref" -- | sha256sum | awk '{print $1}'
