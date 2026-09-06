#!/usr/bin/env bash
# Per-boot startup for the Saboteur 92 environment.
# Provides a headless X server (:99) with software Vulkan so the Godot game can
# render and be screen-captured for GUI testing.
#
# Idempotent: it will not start a second Xvfb if one is already listening on :99.
# Xvfb is launched in a detached session (setsid) so it keeps running after this
# start script returns; a plain `&` background job would otherwise be reaped when
# the start command's process group exits, leaving :99 unavailable to the agent.
set -euo pipefail

DISPLAY_NUM=":99"

if xdpyinfo -display "${DISPLAY_NUM}" >/dev/null 2>&1; then
  echo "Xvfb already running on ${DISPLAY_NUM}."
  exit 0
fi

echo "Starting Xvfb on ${DISPLAY_NUM} (1280x720x24), detached..."
setsid bash -c "exec Xvfb ${DISPLAY_NUM} -screen 0 1280x720x24 -ac +extension GLX +render -noreset" \
  </dev/null >/tmp/xvfb.log 2>&1 &
disown 2>/dev/null || true

# Wait briefly for the server to accept connections.
for _ in $(seq 1 40); do
  xdpyinfo -display "${DISPLAY_NUM}" >/dev/null 2>&1 && break
  sleep 0.25
done

if xdpyinfo -display "${DISPLAY_NUM}" >/dev/null 2>&1; then
  echo "Xvfb ready on ${DISPLAY_NUM}."
else
  echo "WARNING: Xvfb failed to become ready on ${DISPLAY_NUM}; GUI capture may be unavailable." >&2
fi
