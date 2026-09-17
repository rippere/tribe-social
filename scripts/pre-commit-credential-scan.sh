#!/usr/bin/env bash
# pre-commit: block commits containing real-looking secrets in the staged diff.
# Override: SECRETS_OK=1 git commit ...
set -euo pipefail

if [ "${SECRETS_OK:-0}" = "1" ]; then
    echo "pre-commit: SECRETS_OK=1 set — skipping secret scan." >&2
    exit 0
fi

# Patterns for real-looking credentials.
patterns=(
    'rpa_[A-Za-z0-9]{20,}'
    'hf_[A-Za-z0-9]{20,}'
    'sk-[A-Za-z0-9]{20,}'
    'AKIA[0-9A-Z]{16}'
)

# Obvious placeholders to ignore even if they happen to match length-wise.
# Lines containing these tokens are treated as redacted examples.
placeholder_re='(xxxx|XXXX|placeholder|PLACEHOLDER|redacted|REDACTED|your[-_]?key|YOUR[-_]?KEY|example|EXAMPLE|\*\*\*\*|<.*>|changeme|CHANGEME|dummy|DUMMY)'

found=0
joined_re="$(IFS='|'; echo "${patterns[*]}")"

# Only scan added/changed lines (those starting with '+', minus the +++ header),
# and capture which file they belong to.
current_file=""
while IFS= read -r line; do
    case "$line" in
        '+++ b/'*)
            current_file="${line#+++ b/}"
            continue
            ;;
        '+++ '*|'--- '*)
            continue
            ;;
        '+'*)
            content="${line:1}"
            # Skip lines that are clearly redacted examples/placeholders.
            if echo "$content" | grep -Eq "$placeholder_re"; then
                continue
            fi
            if echo "$content" | grep -Eq "$joined_re"; then
                match="$(echo "$content" | grep -Eo "$joined_re" | head -n1)"
                # Mask the middle of the match in the report so we don't print the full secret.
                masked="$(echo "$match" | sed -E 's/(.{6}).*(.{2})/\1…\2/')"
                echo "BLOCKED: possible secret in '${current_file:-<unknown file>}': ${masked}" >&2
                found=1
            fi
            ;;
    esac
done < <(git diff --cached --no-color --unified=0)

if [ "$found" = "1" ]; then
    echo "" >&2
    echo "Commit blocked: real-looking credentials detected in staged changes." >&2
    echo "Remove the secret (or redact it), or override with SECRETS_OK=1 if this is a false positive." >&2
    exit 1
fi

exit 0
