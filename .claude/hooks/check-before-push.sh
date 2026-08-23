#!/usr/bin/env bash
# PreToolUse hook (Bash): blocks pushing commits that haven't been through an
# independent review since they last changed. settings.json's `if` filter is
# only a best-effort prefilter, so this re-checks the actual command from
# stdin itself rather than trusting the filter to have scoped it correctly.
set -euo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}"

payload="$(cat)"
is_push="$(printf '%s' "$payload" | python3 -c '
import json, re, sys

try:
	data = json.load(sys.stdin)
except Exception:
	print("0")
	sys.exit()

command = (data.get("tool_input") or {}).get("command") or ""
segments = re.split(r"[;&|\n]+", command)
found = any(re.match(r"\s*git\s+push\b", segment) for segment in segments)
print("1" if found else "0")
')"

if [ "$is_push" != "1" ]; then
	exit 0
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
	exit 0
fi

marker_file=".claude/.last-reviewed-diff-hash"

if ! current_hash="$("$(dirname "$0")/diff-hash.sh")"; then
	# No safe baseline to diff against (e.g. first push of a brand-new branch
	# with no remote counterpart) — nothing to compare, so don't block.
	exit 0
fi

if [ -f "$marker_file" ] && [ "$(cat "$marker_file")" = "$current_hash" ]; then
	exit 0
fi

reason="The commits about to be pushed have not been independently reviewed yet (or changed since the last review). Before pushing: (1) run an independent review of the diff via the code-review skill or an Agent-tool subagent; (2) record it by running: bash .claude/hooks/mark-reviewed.sh; (3) then retry the push."
printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$reason"
