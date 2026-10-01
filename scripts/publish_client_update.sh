#!/bin/sh
set -eu
if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <windows|android> <artifact>" >&2
  exit 2
fi
platform="$1"; artifact="$2"
case "$platform" in windows|android) ;; *) echo "Unsupported platform" >&2; exit 2;; esac
[ -f "$artifact" ] || { echo "File not found: $artifact" >&2; exit 2; }
target_dir="client_updates/$platform"
mkdir -p "$target_dir"
artifact_name=$(basename "$artifact")
artifact_tmp="$target_dir/.${artifact_name}.tmp.$$"
cp "$artifact" "$artifact_tmp"
mv -f "$artifact_tmp" "$target_dir/$artifact_name"

if [ "$platform" = "windows" ]; then
  source_dir=$(dirname "$artifact")
  blockmap="$artifact.blockmap"
  if [ -f "$blockmap" ]; then
    cp "$blockmap" "$target_dir/.${artifact_name}.blockmap.tmp.$$"
    mv -f "$target_dir/.${artifact_name}.blockmap.tmp.$$" "$target_dir/${artifact_name}.blockmap"
  fi
  if [ -f "$source_dir/latest.yml" ]; then
    cp "$source_dir/latest.yml" "$target_dir/.latest.yml.tmp.$$"
  else
    version=$(printf '%s' "$artifact_name" | sed -n 's/[^0-9]*\([0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*\).*/\1/p')
    [ -n "$version" ] || { echo "Version is missing in artifact filename: $artifact_name" >&2; exit 2; }
    size=$(wc -c < "$artifact" | tr -d ' ')
    sha512=$(openssl dgst -sha512 -binary "$artifact" | base64 | tr -d '\n')
    release_date=$(date -u +%Y-%m-%dT%H:%M:%S.000Z)
    printf 'version: %s\nfiles:\n  - url: %s\n    sha512: %s\n    size: %s\npath: %s\nsha512: %s\nreleaseDate: %s\n' \
      "$version" "$artifact_name" "$sha512" "$size" "$artifact_name" "$sha512" "$release_date" > "$target_dir/.latest.yml.tmp.$$"
  fi
  mv -f "$target_dir/.latest.yml.tmp.$$" "$target_dir/latest.yml"
fi

echo "Published atomically: $target_dir/$artifact_name"
[ "$platform" != "windows" ] || echo "Desktop feed: /ops/client-update/feed/windows/latest.yml"
if command -v docker >/dev/null 2>&1 && docker compose ps web >/dev/null 2>&1; then
  docker compose exec web python manage.py sync_client_versions || true
fi
