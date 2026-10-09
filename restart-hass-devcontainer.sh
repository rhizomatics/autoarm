#!/bin/bash
# Restart the Home Assistant dev instance in this devcontainer, picking up the latest
# custom_components/autoarm code (it's symlinked into HA_CONFIG, but Python only
# reloads it on process restart).
set -euo pipefail

HA_CONFIG="${HA_CONFIG:-/home/vscode/ha-config}"
HASS_BIN="${HASS_BIN:-/workspaces/autoarm/.devcontainer/.venv/bin/hass}"
LOG="$HA_CONFIG/hass.log"

echo "Stopping any running Home Assistant..."
pkill -f "$HASS_BIN -c $HA_CONFIG" 2>/dev/null || true
for _ in $(seq 1 20); do
    pgrep -f "$HASS_BIN -c $HA_CONFIG" >/dev/null 2>&1 || break
    sleep 0.5
done

echo "Starting Home Assistant with the latest autoarm..."
cd "$HA_CONFIG"
nohup "$HASS_BIN" -c "$HA_CONFIG" --debug > "$LOG" 2>&1 &
disown
echo "Home Assistant starting (pid $!), logging to $LOG"

echo "Waiting for it to come up on port 8123..."
for _ in $(seq 1 60); do
    if curl -s -o /dev/null http://localhost:8123/; then
        echo "Home Assistant is up: http://localhost:9123 (forwarded from container port 8123)"
        exit 0
    fi
    sleep 1
done

echo "Home Assistant did not respond within 60s; check $LOG" >&2
exit 1
