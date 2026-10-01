#!/bin/sh
set -eu
cd "$(dirname "$0")"
[ -f keystore.properties ] || { echo "Signing key missing: create keystore.properties + rmes-release.jks first" >&2; exit 2; }
: "${ANDROID_HOME:=${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}}"
export ANDROID_HOME ANDROID_SDK_ROOT="$ANDROID_HOME"
command -v gradle >/dev/null 2>&1 || { echo "Gradle 8.9+ is required" >&2; exit 2; }
gradle --no-daemon clean assembleRelease bundleRelease
cp app/build/outputs/apk/release/app-release.apk RMes-15.1.2.apk
cp app/build/outputs/bundle/release/app-release.aab RMes-15.1.2.aab
echo "READY: $(pwd)/RMes-15.1.2.apk"
echo "READY: $(pwd)/RMes-15.1.2.aab"
