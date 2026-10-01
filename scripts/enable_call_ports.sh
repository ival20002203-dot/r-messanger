#!/usr/bin/env bash
set -euo pipefail
if ! command -v ufw >/dev/null 2>&1; then
  echo "ufw is not installed; no firewall changes made."
  exit 0
fi
sudo ufw allow 3478/tcp comment 'R-Mes TURN TCP' || true
sudo ufw allow 3478/udp comment 'R-Mes TURN UDP' || true
sudo ufw allow 49160:49200/udp comment 'R-Mes TURN relay' || true
sudo ufw status
