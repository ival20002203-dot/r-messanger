#!/usr/bin/env bash
set -euo pipefail
root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
expected_version="13.8.4"
test "$(tr -d '[:space:]' < "$root_dir/VERSION")" = "$expected_version"
python3 -m py_compile "$root_dir/apps/chat/services.py" "$root_dir/apps/chat/views.py" "$root_dir/apps/chat/api.py" "$root_dir/apps/chat/consumers.py" "$root_dir/apps/accounts/views.py" "$root_dir/apps/accounts/presence.py"
node --check "$root_dir/static/app.js"
node --check "$root_dir/static/chat.js"
node --check "$root_dir/static/i18n.js"
node --check "$root_dir/desktop/main.js"
echo "R-Mes $expected_version source validation passed"
