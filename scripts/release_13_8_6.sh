#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
expected_version="13.8.6"

test "$(tr -d '[:space:]' < "$root_dir/VERSION")" = "$expected_version"
python3 -m py_compile \
  "$root_dir/apps/accounts/presence.py" \
  "$root_dir/apps/accounts/views.py" \
  "$root_dir/apps/chat/consumers.py"
node --check "$root_dir/static/app.js"

echo "R-Mes $expected_version presence lifecycle validation passed"
