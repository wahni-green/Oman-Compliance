#!/usr/bin/env bash
# PreToolUse hook (Bash): blocks pushing commits that haven't been through an
# independent review since they last changed. settings.json's `if` filter is
# only a best-effort prefilter, so this re-checks the actual command from
# stdin itself rather than trusting the filter to have scoped it correctly.
set -euo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}"

payload="$(cat)"
# Parses out the actual `<remote> <refspec>` arguments of a `git push`, so the
# baseline diff-hash.sh computes matches what's really being pushed rather
# than always assuming "current branch vs its own upstream" — otherwise
# `git push <other-remote> <other-refspec>` would be checked against the
# wrong commit range and a stale marker could wrongly authorize it. Tokenizes
# each segment (rather than a single regex on the raw text) so env-var
# prefixes (`FOO=bar git push`) and git's own global options
# (`git -c x=y push`) before the `push` subcommand are still detected.
push_info="$(printf '%s' "$payload" | python3 -c '
import json, re, sys

try:
	data = json.load(sys.stdin)
except Exception:
	print("0")
	sys.exit()

command = (data.get("tool_input") or {}).get("command") or ""
segments = re.split(r"[;&|\n]+", command)

ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# git global options that consume a following value token (only when not
# already given in --flag=value form).
GLOBAL_VALUE_FLAGS = {"-c", "-C", "--git-dir", "--work-tree", "--namespace", "--super-prefix", "--exec-path"}

def find_push_args(tokens):
	i = 0
	while i < len(tokens) and ENV_ASSIGNMENT.match(tokens[i]):
		i += 1
	if i >= len(tokens) or tokens[i] != "git":
		return None
	i += 1
	while i < len(tokens) and tokens[i].startswith("-"):
		flag = tokens[i]
		i += 1
		if flag in GLOBAL_VALUE_FLAGS and "=" not in flag:
			i += 1
	if i >= len(tokens) or tokens[i] != "push":
		return None
	return tokens[i + 1 :]

push_args = None
for segment in segments:
	result = find_push_args(segment.split())
	if result is not None:
		push_args = result
		break

if push_args is None:
	print("0")
	sys.exit()

# Flags that consume a following value token, so it is not mistaken for the
# remote/refspec positional arguments.
VALUE_FLAGS = {"--repo", "--receive-pack", "--exec", "--push-option", "-o"}
# Flags that push a scope this hook cannot represent as a single ref diff.
AMBIGUOUS_FLAGS = {"--all", "--mirror", "--branches", "--tags"}

positional = []
skip_next = False
ambiguous = False
for token in push_args:
	if skip_next:
		skip_next = False
		continue
	if token.startswith("-"):
		if token in VALUE_FLAGS:
			skip_next = True
		elif token in AMBIGUOUS_FLAGS:
			ambiguous = True
		continue
	positional.append(token)

# More than one refspec, or a glob refspec, is also not representable as a
# single ref diff — reject rather than silently checking/ignoring only part
# of what would actually be pushed.
if not ambiguous and len(positional) > 2:
	ambiguous = True

remote = positional[0] if positional else "origin"
refspec = positional[1] if len(positional) > 1 else ""
refspec = refspec.lstrip("+")

if not ambiguous and "*" in refspec:
	ambiguous = True

if ambiguous:
	print("1")
	print("AMBIGUOUS")
	sys.exit()

if ":" in refspec:
	local_ref, _, remote_ref = refspec.partition(":")
elif refspec:
	local_ref = remote_ref = refspec
else:
	local_ref, remote_ref = "", ""

print("1")
print(remote)
print(local_ref)
print(remote_ref)
')"

is_push="$(printf '%s\n' "$push_info" | sed -n '1p')"
if [ "$is_push" != "1" ]; then
	exit 0
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
	exit 0
fi

line2="$(printf '%s\n' "$push_info" | sed -n '2p')"
if [ "$line2" = "AMBIGUOUS" ]; then
	reason="This push form (--all/--mirror/--tags/--branches, a glob refspec, or more than one refspec in one command) can't be represented as a single reviewed ref diff, so it's rejected rather than silently checking or ignoring part of what would be pushed. Push one explicit <remote> <local:remote> refspec at a time instead."
	printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$reason"
	exit 0
fi

remote="$line2"
local_ref="$(printf '%s\n' "$push_info" | sed -n '3p')"
remote_ref="$(printf '%s\n' "$push_info" | sed -n '4p')"

[ -n "$local_ref" ] || local_ref="HEAD"
if [ -z "$remote_ref" ]; then
	remote_ref="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
fi

marker_file=".claude/.last-reviewed-diff-hash"

if ! current_hash="$("$(dirname "$0")/diff-hash.sh" "$remote" "$local_ref" "$remote_ref")"; then
	# No safe baseline to diff against (e.g. first push of a brand-new branch
	# with no remote counterpart) — nothing to compare, so don't block.
	exit 0
fi

if [ -f "$marker_file" ] && [ "$(cat "$marker_file")" = "$current_hash" ]; then
	exit 0
fi

reason="The commits about to be pushed have not been independently reviewed yet (or changed since the last review). Before pushing: (1) run an independent review of the diff via the code-review skill or an Agent-tool subagent; (2) record it by running: bash .claude/hooks/mark-reviewed.sh; (3) then retry the push."
printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$reason"
