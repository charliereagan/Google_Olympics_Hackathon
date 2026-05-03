#!/usr/bin/env bash
# Day-1 CI gate: assert Apache 2.0 license is present and detectable.
# Auto-DQ trigger if missing on submission day. Wired into pre-commit + GH Actions.
# (BUILD_SPEC §13 hard gate; PROJECT_BRIEF §8.)

set -euo pipefail

# Resolve repo root from the script's location so this works whether invoked
# from the repo root or anywhere else.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

LICENSE_FILE="${REPO_ROOT}/LICENSE"
README_FILE="${REPO_ROOT}/README.md"

fail() {
  echo "FAIL: Apache 2.0 license check — $1" >&2
  echo "" >&2
  echo "How to fix:" >&2
  echo "  1. LICENSE in repo root must contain 'Apache License' AND 'Version 2.0'." >&2
  echo "  2. README.md first ~500 chars must mention 'Apache License'." >&2
  echo "  3. GitHub repo About sidebar must show the Apache 2.0 badge — set in repo Settings." >&2
  echo "" >&2
  echo "Auto-DQ trigger if missing on submission day (PROJECT_BRIEF §8)." >&2
  exit 1
}

# 1. LICENSE file exists in repo root.
if [[ ! -f "${LICENSE_FILE}" ]]; then
  fail "LICENSE file missing at ${LICENSE_FILE}"
fi

# 2. LICENSE contains both 'Apache License' AND 'Version 2.0'.
if ! grep -q "Apache License" "${LICENSE_FILE}"; then
  fail "LICENSE does not contain the literal 'Apache License'"
fi
if ! grep -q "Version 2.0" "${LICENSE_FILE}"; then
  fail "LICENSE does not contain the literal 'Version 2.0'"
fi

# 3. README first paragraph (first ~500 chars) mentions 'Apache License'.
if [[ ! -f "${README_FILE}" ]]; then
  fail "README.md missing at ${README_FILE}"
fi
README_HEAD="$(head -c 500 "${README_FILE}")"
if ! grep -q "Apache License" <<<"${README_HEAD}"; then
  fail "README.md first ~500 chars do not mention 'Apache License'"
fi

echo "✓ Apache 2.0 license check passed"
echo "  - LICENSE: ${LICENSE_FILE}"
echo "  - README:  ${README_FILE} (mentions Apache License in first 500 chars)"
exit 0
