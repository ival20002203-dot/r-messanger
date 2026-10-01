#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
value=$(grep -E '^WEB_ACCESS_ENABLED=' .env 2>/dev/null | tail -1 | cut -d= -f2- || true)
[[ -z "$value" ]] && value=1
printf 'WEB_ACCESS_ENABLED=%s\n' "$value"
